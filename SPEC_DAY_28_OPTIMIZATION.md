# Day 28: Оптимизация и адаптация локальной LLM

## Обзор

Добавление расширенных параметров оптимизации для локальных LLM (Ollama) и системы conditional prompts с автоматическим выбором шаблона на основе типа запроса.

## Целевая задача

Оптимизация качества общего чата через:
1. Расширенные параметры генерации (num_ctx, num_predict, repeat_penalty, num_gpu/num_thread)
2. Условные system prompts (Code, Creative, Analysis, General)
3. Per-conversation настройки

---

## 1. Расширенные параметры Ollama

### 1.1 Новые параметры в UI

| Параметр | Описание | UI элемент | Диапазон |
|----------|----------|------------|----------|
| `num_ctx` | Размер контекстного окна | Slider с подсказками | 2048-32768 |
| `num_predict` | Макс. токенов в ответе | Number input | 128-4096 |
| `repeat_penalty` | Штраф за повторения | Slider | 1.0-2.0 |
| `num_gpu` | GPU слои | Number input | 0-99 |
| `num_thread` | CPU потоки | Number input | 1-16 |

### 1.2 UI для num_ctx (Slider с подсказками)

```
[====|============] 8K

2K    4K    8K    16K    32K
└─ Fast  └─ Balanced  └─ Max quality
   ~4GB     ~8GB         ~16GB RAM
```

При выборе показывать:
- Текущее значение (e.g., "8192 tokens")
- Ожидаемое использование памяти
- Предупреждение если превышает лимиты модели

### 1.3 Query Ollama Limits

Перед отображением UI запросить лимиты у Ollama:
```
GET /api/show
POST /api/show {"name": "qwen2.5:14b"}
```

Ответ содержит:
- `parameters.num_ctx` — дефолтный context length модели
- `model_info.context_length` — максимальный поддерживаемый

Показывать в UI: "Model supports up to 32K context"

### 1.4 Передача в Ollama API

Через `options` object в запросе:
```json
{
  "model": "qwen2.5:14b",
  "messages": [...],
  "options": {
    "num_ctx": 8192,
    "num_predict": 2048,
    "repeat_penalty": 1.1,
    "num_gpu": 99,
    "num_thread": 8
  }
}
```

Изменить `ollama_client.py` для передачи параметров.

---

## 2. Conditional Prompts

### 2.1 Категории

| Категория | Описание | Дефолт num_ctx | Дефолт temperature |
|-----------|----------|----------------|-------------------|
| `code` | Программирование, дебаг, API | 16384 | 0.2 |
| `creative` | Тексты, сторителлинг | 8192 | 0.9 |
| `analysis` | Анализ данных, math, логика | 16384 | 0.3 |
| `general` | Общие вопросы, fallback | 4096 | 0.7 |

### 2.2 LLM-классификатор

**Архитектура**: Первый запрос к LLM для классификации, затем основной запрос с выбранным prompt.

**Classifier prompt**:
```
Классифицируй следующий запрос пользователя в одну из категорий: code, creative, analysis, general.

Запрос: "{user_message}"

Ответь ТОЛЬКО в формате JSON:
{"category": "code", "confidence": 0.9}
```

**Формат ответа**: JSON с полями `category` и `confidence`

**Кэширование**: В рамках одной сессии/разговора. Ключ — первые 100 символов запроса (normalized).

**Fallback**: При ошибке классификатора (timeout, parse error) → использовать `general`

### 2.3 System Prompts по категориям

**Язык**: Русский (сохранить текущее поведение)

**Режим override**: Кастомный prompt полностью заменяет дефолтный

**Code prompt**:
```
Ты опытный программист-эксперт. Отвечай точно, с примерами кода.
Используй правильное форматирование (markdown code blocks).
Объясняй сложные концепции простым языком.
```

**Creative prompt**:
```
Ты креативный писатель с богатым воображением.
Создавай оригинальный, увлекательный контент.
Используй яркие образы и выразительный язык.
```

**Analysis prompt**:
```
Ты аналитик с логическим мышлением.
Структурируй ответы. Приводи аргументы и доказательства.
Если нужны вычисления — показывай ход решения.
```

**General prompt**:
```
Ты полезный ассистент. Отвечай чётко и по существу.
Если вопрос неоднозначен — уточни.
```

### 2.4 Редактирование шаблонов

Пользователь может полностью редактировать все 4 шаблона через UI.
Валидация: НЕТ (доверять пользователю — локальное приложение).

Хранение: localStorage
```json
{
  "promptTemplates": {
    "code": "...",
    "creative": "...",
    "analysis": "...",
    "general": "..."
  }
}
```

---

## 3. UI Architecture

### 3.1 Новый сайдбар

**Позиция**: Справа от чата
**Поведение**: Сворачиваемый (collapsed по умолчанию?)
**Mobile**: Не поддерживается (desktop-only)

**Секции сайдбара**:
```
┌─────────────────────────┐
│ ⚙️ Настройки           ×│
├─────────────────────────┤
│ 📊 Metrics              │
│ ┌─────────────────────┐ │
│ │ 45.2 tok/s          │ │
│ │ Latency: 1.2s       │ │
│ │ Context: 4K/16K     │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ 🎯 Режим: [Auto ▼]      │
│   💻 Technical          │
├─────────────────────────┤
│ 🔧 Параметры            │
│                         │
│ Context (num_ctx)       │
│ [====|====] 8K          │
│ 2K  4K  8K  16K  32K    │
│                         │
│ Max tokens (num_predict)│
│ [    2048    ]          │
│                         │
│ Repeat penalty          │
│ [==|========] 1.1       │
│                         │
│ GPU layers              │
│ [   99   ]              │
│                         │
│ CPU threads             │
│ [    8   ]              │
└─────────────────────────┘
```

### 3.2 Mode Badge

В интерфейсе чата показывать текущий режим:
```
💻 Technical mode | ✨ Creative mode | 📊 Analysis mode | 💬 General mode
```

Появляется после классификации, рядом с ответом или в хедере чата.

### 3.3 Mode Override (Dropdown)

Рядом с полем ввода (или в сайдбаре):
```
Режим: [Auto ▼]
       ├─ Auto (определять автоматически)
       ├─ 💻 Code / Technical
       ├─ ✨ Creative / Writing
       ├─ 📊 Analysis / Reasoning
       └─ 💬 General
```

Если выбран не Auto — пропустить классификацию.

### 3.4 Per-conversation Override

Настройки можно менять для конкретного чата (не только глобально).

**Индикация**: Tooltip на иконке настроек
```
При наведении: "Изменены: num_ctx, temperature"
```

**Хранение**: В localStorage вместе с conversation data
```json
{
  "conversations": {
    "conv-123": {
      "messages": [...],
      "settingsOverride": {
        "num_ctx": 16384,
        "temperature": 0.3
      }
    }
  }
}
```

### 3.5 Regenerate Button

Простая кнопка "Перегенерировать" под ответом.
Без выбора режима (использует текущий или переклассифицирует).

### 3.6 Auto-save

Все изменения настроек сохраняются автоматически (debounced, ~500ms).
Без кнопки "Сохранить".

---

## 4. Backend Changes

### 4.1 Новые поля в ChatRequest (schemas.py)

```python
class OllamaOptions(BaseModel):
    num_ctx: Optional[int] = None
    num_predict: Optional[int] = None
    repeat_penalty: Optional[float] = None
    num_gpu: Optional[int] = None
    num_thread: Optional[int] = None

class ChatRequest(BaseModel):
    # ... existing fields ...
    ollama_options: Optional[OllamaOptions] = None
    prompt_mode: Optional[Literal["auto", "code", "creative", "analysis", "general"]] = "auto"
```

### 4.2 Classifier Service (новый файл)

`app/app/services/prompt_classifier.py`:

```python
class PromptClassifier:
    CATEGORIES = ["code", "creative", "analysis", "general"]

    def __init__(self, ollama_client: OllamaClient):
        self.client = ollama_client
        self._session_cache: dict[str, str] = {}

    async def classify(self, message: str) -> ClassificationResult:
        cache_key = self._normalize(message[:100])
        if cache_key in self._session_cache:
            return self._session_cache[cache_key]

        try:
            result = await self._call_classifier(message)
            self._session_cache[cache_key] = result
            return result
        except Exception:
            return ClassificationResult(category="general", confidence=0.0)

    def clear_session_cache(self):
        self._session_cache.clear()
```

### 4.3 Prompt Templates Store

`app/app/services/prompt_templates.py`:

```python
DEFAULT_TEMPLATES = {
    "code": "Ты опытный программист-эксперт...",
    "creative": "Ты креативный писатель...",
    "analysis": "Ты аналитик с логическим мышлением...",
    "general": "Ты полезный ассистент...",
}

CATEGORY_DEFAULTS = {
    "code": {"num_ctx": 16384, "temperature": 0.2},
    "creative": {"num_ctx": 8192, "temperature": 0.9},
    "analysis": {"num_ctx": 16384, "temperature": 0.3},
    "general": {"num_ctx": 4096, "temperature": 0.7},
}
```

### 4.4 Изменения в OllamaClient

`app/app/services/ollama_client.py`:

```python
async def chat(
    self,
    messages: list[dict],
    model: str,
    options: Optional[dict] = None,  # NEW
    **kwargs
) -> OllamaResponse:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if options:
        payload["options"] = options
    # ...
```

### 4.5 Изменения в ProviderRouter

Добавить логику:
1. Если `prompt_mode == "auto"` → вызвать classifier
2. Применить дефолты категории к параметрам
3. Merge с user overrides
4. Передать в Ollama

### 4.6 Новый эндпоинт: Ollama Model Info

`GET /api/ollama/model/{model_name}`:
```json
{
  "name": "qwen2.5:14b",
  "context_length": 32768,
  "default_num_ctx": 4096,
  "parameters": {...}
}
```

---

## 5. Frontend Changes

### 5.1 Новые компоненты

```
frontend/src/components/
├── sidebar/
│   ├── SettingsSidebar.tsx      # Основной сайдбар
│   ├── MetricsSection.tsx       # Секция метрик
│   ├── ModeSelector.tsx         # Выбор режима (Auto/Code/etc)
│   ├── ParametersSection.tsx    # Параметры Ollama
│   └── ContextSlider.tsx        # Slider для num_ctx
├── chat/
│   └── ModeBadge.tsx            # Бейдж режима
```

### 5.2 Новый store

`frontend/src/store/optimizationStore.ts`:

```typescript
interface OptimizationState {
  // Global defaults
  promptMode: 'auto' | 'code' | 'creative' | 'analysis' | 'general';
  promptTemplates: Record<string, string>;

  // Ollama parameters
  num_ctx: number;
  num_predict: number;
  repeat_penalty: number;
  num_gpu: number;
  num_thread: number;

  // Model limits (from Ollama)
  modelLimits: {
    max_context: number;
    default_context: number;
  } | null;

  // Per-conversation overrides
  conversationOverrides: Record<string, Partial<OptimizationState>>;
}
```

### 5.3 Изменения в settingsStore

Добавить:
- `sidebarCollapsed: boolean`
- `showModeBadge: boolean`

### 5.4 API Client

Добавить в `api.ts`:
```typescript
async getModelInfo(model: string): Promise<ModelInfo> {
  const response = await fetch(`/api/ollama/model/${model}`);
  return response.json();
}
```

---

## 6. Риски и митигации

### 6.1 Главный риск: Сложность UX

**Митигация**:
- Сайдбар свёрнут по умолчанию
- Auto режим работает без вмешательства пользователя
- Дефолты подобраны оптимально для каждой категории
- Простой режим (без conditional prompts) всё ещё доступен

### 6.2 Latency от классификации

**Митигация**:
- Кэширование в рамках сессии
- Возможность отключить Auto и выбрать режим вручную
- Fallback на general при ошибках

### 6.3 Неточная классификация

**Митигация**:
- Показывать бейдж режима — пользователь видит что выбрано
- Override через dropdown
- Кнопка "Перегенерировать"

---

## 7. Testing Strategy

**Визуальное тестирование в UI**:
- Пользователь оценивает качество ответов
- Metrics panel показывает tokens/sec, latency
- Можно сравнить разные настройки вручную

**Unit tests**:
- `test_prompt_classifier.py` — тесты классификатора
- `test_ollama_options.py` — передача параметров в Ollama
- `test_prompt_templates.py` — загрузка/сохранение шаблонов

---

## 8. Файлы для изменения

### Backend
- `app/app/schemas.py` — новые поля OllamaOptions, prompt_mode
- `app/app/services/ollama_client.py` — передача options
- `app/app/services/provider_router.py` — интеграция classifier
- `app/app/services/prompt_classifier.py` — НОВЫЙ
- `app/app/services/prompt_templates.py` — НОВЫЙ
- `app/app/main.py` — новый endpoint /api/ollama/model/{name}

### Frontend
- `frontend/src/components/sidebar/` — НОВАЯ директория
- `frontend/src/store/optimizationStore.ts` — НОВЫЙ
- `frontend/src/store/settingsStore.ts` — добавить sidebarCollapsed
- `frontend/src/components/chat/ModeBadge.tsx` — НОВЫЙ
- `frontend/src/components/chat/ChatInput.tsx` — добавить mode selector
- `frontend/src/services/api.ts` — новые endpoints
- `frontend/src/types/index.ts` — новые типы

---

## 9. Acceptance Criteria

1. ✅ Пользователь может настроить num_ctx, num_predict, repeat_penalty, num_gpu, num_thread через UI
2. ✅ Slider для num_ctx показывает подсказки по RAM и лимитам модели
3. ✅ Conditional prompts автоматически определяют категорию запроса
4. ✅ В UI показывается бейдж выбранного режима
5. ✅ Пользователь может переопределить режим вручную через dropdown
6. ✅ Настройки сохраняются per-conversation
7. ✅ Metrics отображаются в сайдбаре в реальном времени
8. ✅ Сайдбар сворачиваемый и не мешает основному чату
9. ✅ При ошибке классификатора используется general режим
10. ✅ Prompt-шаблоны полностью редактируемы пользователем
