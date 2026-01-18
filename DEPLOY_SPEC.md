# Спецификация CI/CD пайплайна для ChatGPT Proxy

## Обзор

Автоматический пайплайн для сборки Docker-образа и деплоя приложения ChatGPT Proxy на VPS при каждом коммите в `main`.

## Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   GitHub    │────▶│   GitHub    │────▶│  Docker Hub │────▶│    VPS      │
│   (main)    │     │   Actions   │     │  Registry   │     │  (SSH)      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
     push            build+push           pull               deploy
```

## Принятые решения

| Аспект | Решение | Обоснование |
|--------|---------|-------------|
| CI система | GitHub Actions | Интеграция с репозиторием, бесплатно для публичных репо |
| Registry | Docker Hub | Простота, надёжность, нативная поддержка в Actions |
| Деплой | SSH + docker compose | VPS без оркестрации, минимум зависимостей |
| Downtime | Простой restart | Приемлемо несколько секунд недоступности |
| Откат | Ручной | Уведомление при ошибке, разработчик решает |
| Тесты | Нет | Разработчик проверяет локально |
| Frontend | Multi-stage Docker | Всё в одном Dockerfile |
| RAG | Отключен в проде | RAG_ENABLED=false |
| Health check | HTTP /health endpoint | Проверка после деплоя |
| Теги образов | latest + git SHA | Баланс простоты и трейсабилити |
| Cleanup | Автоматический | Удаление старых образов в CI |

## Триггеры

- Push в ветку `main` → полный пайплайн (build + deploy)
- Ручной запуск через `workflow_dispatch` → выбор тега для деплоя

## Секреты (GitHub Secrets)

| Имя | Описание |
|-----|----------|
| `DOCKER_USERNAME` | Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub access token (не пароль!) |
| `DEPLOY_HOST` | IP или hostname VPS |
| `DEPLOY_USER` | SSH username на VPS |
| `DEPLOY_KEY` | Приватный SSH ключ (Ed25519 рекомендуется) |

## Переменные окружения на сервере

Файл `/opt/chatgpt-proxy/.env`:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
RAG_ENABLED=false
```

## Риски и митигации

### 1. Утечка секретов
- **Риск**: SSH-ключи или API keys попадут в логи
- **Митигация**:
  - Использовать `${{ secrets.* }}` только в защищённых контекстах
  - Не выводить переменные в echo/debug
  - GitHub автоматически маскирует секреты в логах

### 2. Сломанный деплой
- **Риск**: Новый образ не работает, прод недоступен
- **Митигация**:
  - Health check после деплоя с таймаутом
  - Сохранение предыдущего тега для ручного отката
  - SSH доступ для экстренного вмешательства

### 3. Сложность поддержки
- **Риск**: Пайплайн станет сложным
- **Митигация**:
  - Минимум шагов, без over-engineering
  - Понятные имена jobs и steps
  - Комментарии в критичных местах

---

## Файлы конфигурации

### `.github/workflows/deploy.yml`

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      tag:
        description: 'Image tag to deploy (default: latest)'
        required: false
        default: 'latest'

env:
  IMAGE_NAME: ${{ secrets.DOCKER_USERNAME }}/chatgpt-proxy
  DEPLOY_PATH: /opt/chatgpt-proxy

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      sha_short: ${{ steps.vars.outputs.sha_short }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Get short SHA
        id: vars
        run: echo "sha_short=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ env.IMAGE_NAME }}:latest
            ${{ env.IMAGE_NAME }}:${{ steps.vars.outputs.sha_short }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest

    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          script: |
            cd ${{ env.DEPLOY_PATH }}

            # Pull новый образ
            docker compose pull

            # Перезапуск с новым образом
            docker compose up -d --remove-orphans

            # Ожидание запуска (10 секунд)
            sleep 10

            # Health check
            if curl -sf http://localhost:8333/health > /dev/null; then
              echo "✅ Health check passed"
            else
              echo "❌ Health check failed"
              docker compose logs --tail=50
              exit 1
            fi

  cleanup:
    needs: deploy
    runs-on: ubuntu-latest
    if: success()

    steps:
      - name: Cleanup old images on server
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          script: |
            # Удалить неиспользуемые образы старше 7 дней
            docker image prune -a --force --filter "until=168h"

            # Показать оставшееся место
            df -h /var/lib/docker
```

### `docker-compose.prod.yml`

```yaml
version: "3.8"

services:
  chatgpt-proxy:
    image: ${DOCKER_USERNAME:-your-username}/chatgpt-proxy:latest
    container_name: chatgpt-proxy
    restart: unless-stopped
    ports:
      - "8333:8333"
    env_file:
      - .env
    environment:
      - RAG_ENABLED=false
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8333/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### `Dockerfile` (multi-stage с frontend)

```dockerfile
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --only=production

COPY frontend/ ./
RUN npm run build

# Stage 2: Python application
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копирование backend
COPY app/ ./app/

# Копирование собранного frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8333/health || exit 1

EXPOSE 8333

CMD ["uvicorn", "app.app.main:app", "--host", "0.0.0.0", "--port", "8333"]
```

---

## Инструкция по настройке

### 1. Подготовка VPS

```bash
# Создать директорию
sudo mkdir -p /opt/chatgpt-proxy
sudo chown $USER:$USER /opt/chatgpt-proxy

# Скопировать docker-compose.prod.yml
cd /opt/chatgpt-proxy
# Переименовать в docker-compose.yml для удобства
curl -o docker-compose.yml <URL_TO_RAW_FILE>

# Создать .env
cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
RAG_ENABLED=false
EOF

chmod 600 .env
```

### 2. Настройка GitHub Secrets

1. Settings → Secrets and variables → Actions
2. Добавить:
   - `DOCKER_USERNAME`: ваш Docker Hub username
   - `DOCKER_PASSWORD`: Docker Hub access token
   - `DEPLOY_HOST`: IP вашего VPS
   - `DEPLOY_USER`: SSH username
   - `DEPLOY_KEY`: содержимое `~/.ssh/id_ed25519` (приватный ключ)

### 3. SSH ключ для деплоя

```bash
# На локальной машине
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deploy_key

# Добавить публичный ключ на VPS
ssh-copy-id -i ~/.ssh/deploy_key.pub user@your-vps

# Приватный ключ добавить в GitHub Secrets как DEPLOY_KEY
cat ~/.ssh/deploy_key
```

### 4. Проверка health endpoint

Убедитесь, что приложение отвечает на `/health`:

```python
# В app/app/main.py
@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

---

## Ручной откат

При проблемах с новой версией:

```bash
ssh user@vps

cd /opt/chatgpt-proxy

# Посмотреть доступные теги
docker images | grep chatgpt-proxy

# Откатиться на конкретный SHA
docker compose down
docker compose up -d --pull=never -e IMAGE_TAG=abc1234

# Или вручную отредактировать docker-compose.yml
# Изменить :latest на :abc1234
```

---

## Troubleshooting

### Деплой зависает

```bash
# Проверить SSH подключение
ssh -vvv user@vps

# Проверить права на директорию
ls -la /opt/chatgpt-proxy
```

### Health check fails

```bash
# Посмотреть логи контейнера
docker compose logs --tail=100

# Проверить, слушает ли порт
ss -tlnp | grep 8333

# Проверить .env файл
cat /opt/chatgpt-proxy/.env
```

### Disk space issues

```bash
# Очистить все неиспользуемые ресурсы Docker
docker system prune -a --volumes

# Проверить место
df -h
```

---

## Дальнейшие улучшения (out of scope)

- [ ] Добавить staging окружение
- [ ] Blue-green deployment для zero-downtime
- [ ] Автоматический откат при failed health check
- [ ] Telegram/Slack уведомления
- [ ] Тесты перед деплоем
- [ ] Semantic versioning
