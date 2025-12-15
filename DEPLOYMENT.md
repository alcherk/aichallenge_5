# Deployment Guide

Complete guide for deploying the ChatGPT Proxy application with the new React + TypeScript frontend.

## Architecture Overview

The application now uses a modern dual-frontend architecture:

- **Development**: FastAPI backend (port 8333) + Vite dev server (port 5173) with proxy
- **Production**: FastAPI serves built React app from `frontend/dist` + API endpoints

## Development Setup

### Option 1: Dual Server (Recommended for Frontend Development)

Run backend and frontend separately for hot-reloading:

**Terminal 1 - Backend:**
```bash
cd /Users/lex/Projects/ai/AI_Challenge_5/week1_day1
source .venv/bin/activate
export OPENAI_API_KEY="your-key-here"
uvicorn app.app.main:app --reload --port 8333
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
# Opens at http://localhost:5173
# API requests proxied to localhost:8333
```

### Option 2: Single Server (Tests Production Build)

Build frontend first, then run backend:

```bash
# Build frontend
cd frontend
npm run build

# Run backend (serves built frontend)
cd ..
source .venv/bin/activate
export OPENAI_API_KEY="your-key-here"
uvicorn app.app.main:app --port 8333

# Opens at http://localhost:8333
```

## Production Deployment

### Docker (Recommended)

The application uses multi-stage Docker build:

**Build the image:**
```bash
docker build -t chatgpt-proxy .
```

**Run the container:**
```bash
docker run -d \
  --name chatgpt-proxy \
  -e OPENAI_API_KEY="your-api-key" \
  -e OPENAI_MODEL="gpt-4o-mini" \
  -p 8333:8333 \
  --restart unless-stopped \
  chatgpt-proxy
```

**Access:**
- Application: http://localhost:8333
- Health check: http://localhost:8333/health
- API: http://localhost:8333/api/chat

### Docker Compose

```bash
# Set environment variables
export OPENAI_API_KEY="your-key-here"
export OPENAI_MODEL="gpt-4o-mini"

# Start services
docker compose up -d --build

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### VPS Deployment

**Prerequisites:**
- VPS with Docker installed
- Domain name (optional)
- SSL certificate (optional, recommended)

**Steps:**

1. **Copy project to VPS:**
```bash
# Using git
ssh user@your-vps
git clone https://github.com/your-repo/chatgpt-proxy.git
cd chatgpt-proxy

# Or using scp
scp -r /Users/lex/Projects/ai/AI_Challenge_5/week1_day1 user@your-vps:/path/to/app
```

2. **Build and run:**
```bash
# On VPS
cd chatgpt-proxy
docker build -t chatgpt-proxy .

docker run -d \
  --name chatgpt-proxy \
  -e OPENAI_API_KEY="your-key" \
  -e OPENAI_MODEL="gpt-4o-mini" \
  -p 8333:8333 \
  --restart unless-stopped \
  chatgpt-proxy
```

3. **Configure firewall:**
```bash
# Allow port 8333
sudo ufw allow 8333/tcp
sudo ufw reload
```

4. **Access application:**
- Direct: http://your-vps-ip:8333
- Or set up reverse proxy (nginx/Caddy)

### Reverse Proxy (Nginx)

**Example nginx configuration:**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8333;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # SSE streaming support
        proxy_buffering off;
        proxy_cache off;
    }
}
```

**Enable SSL with Certbot:**
```bash
sudo certbot --nginx -d your-domain.com
```

## Environment Variables

### Required

- `OPENAI_API_KEY` - Your OpenAI API key

### Optional

- `OPENAI_MODEL` - Default: `gpt-4o-mini`
- `OPENAI_API_BASE` - Default: `https://api.openai.com/v1`
- `REQUEST_TIMEOUT_SECONDS` - Default: `60`
- `APP_HOST` - Default: `0.0.0.0`
- `APP_PORT` - Default: `8333`
- `MCP_CONFIG_PATH` - Path to MCP server config JSON (optional; disabled by default)
- `WORKSPACE_ROOT` - Workspace root for filesystem-like MCP tools (default: repo root)

## Frontend Features

The new React frontend includes:

✅ **Chat Interface:**
- Real-time SSE streaming
- Markdown rendering
- JSON syntax highlighting
- Auto-scroll to latest message

✅ **Settings Panel:**
- Model selection (GPT-4o, GPT-4 Turbo, GPT-4o Mini, etc.)
- Temperature control (0.0 - 2.0)
- System prompt customization
- Compression threshold

✅ **Metrics Panel:**
- Token usage (input/output/total)
- Cost calculation per request
- Context window usage with visual indicator
- Session totals
- Response time tracking

✅ **Data Persistence:**
- Conversation history (localStorage)
- Settings (localStorage)
- Metrics (localStorage)

## Troubleshooting

### Frontend not loading

**Check if build exists:**
```bash
ls frontend/dist/
# Should show index.html, assets/, etc.
```

**Rebuild frontend:**
```bash
cd frontend
npm run build
```

### Backend not serving React app

**Check backend logs:**
```bash
# The backend should log which frontend it's using
# Look for: "Serving React frontend" or "Serving legacy frontend"
```

**Force rebuild Docker image:**
```bash
docker build --no-cache -t chatgpt-proxy .
```

### API proxy not working in development

**Verify Vite dev server is running:**
```bash
cd frontend
npm run dev
# Should show: http://localhost:5173
```

**Check vite.config.ts proxy settings:**
```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8333',
    '/health': 'http://localhost:8333'
  }
}
```

### CORS errors

In production, CORS is configured to allow all origins (`"*"`). For tighter security, update `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Performance Optimization

### Frontend Bundle Size

Current production build:
- Total: ~374KB (gzipped: ~116KB)
- CSS: ~15KB (gzipped: ~4KB)

To analyze bundle:
```bash
cd frontend
npm run build
# Check dist/ folder sizes
```

### Backend Performance

- SSE streaming for real-time responses
- No server-side state (stateless)
- Uvicorn with async/await
- Context compression to reduce token usage

## Security Considerations

1. **Never commit API keys** - Use environment variables
2. **Enable HTTPS** in production (use reverse proxy)
3. **Restrict CORS** origins in production
4. **Set request rate limiting** (optional, via nginx/middleware)
5. **Validate input** - Already implemented in Pydantic schemas

## Monitoring

### Health Check

```bash
curl http://localhost:8333/health
# Response: {"status":"ok"}
```

### Docker Logs

```bash
# View logs
docker logs chatgpt-proxy

# Follow logs
docker logs -f chatgpt-proxy

# Last 100 lines
docker logs --tail 100 chatgpt-proxy
```

### Metrics

The frontend tracks:
- Total requests
- Total cost
- Token usage per request
- Response times

All metrics stored in browser localStorage.

## Updating the Application

**Pull latest changes:**
```bash
git pull origin main
```

**Rebuild Docker image:**
```bash
docker build -t chatgpt-proxy .
```

**Restart container:**
```bash
docker stop chatgpt-proxy
docker rm chatgpt-proxy
docker run -d --name chatgpt-proxy ... # use same run command
```

**Or with Docker Compose:**
```bash
docker compose down
docker compose up -d --build
```

## Backup & Restore

**User data** is stored in browser localStorage:
- Conversation history
- Settings
- Metrics

To preserve data across browsers/devices, implement server-side storage (future enhancement).

## Support

For issues or questions:
1. Check logs: `docker logs chatgpt-proxy`
2. Verify environment variables
3. Test health endpoint: `curl http://localhost:8333/health`
4. Check OpenAI API key validity
