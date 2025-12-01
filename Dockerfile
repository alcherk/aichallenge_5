FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8333

EXPOSE 8333

CMD ["uvicorn", "app.app.main:app", "--host", "0.0.0.0", "--port", "8333"]
