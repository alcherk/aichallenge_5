# Multi-stage build: Frontend (React + TypeScript)
FROM node:18-slim AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build frontend
RUN npm run build

# Final stage: Backend (Python + FastAPI) + Frontend build
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY app ./app

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Environment variables
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8333

EXPOSE 8333

CMD ["uvicorn", "app.app.main:app", "--host", "0.0.0.0", "--port", "8333"]
