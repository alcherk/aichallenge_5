#!/bin/bash
# Server setup script for ChatGPT Proxy deployment
# Run this on your VPS to prepare for CI/CD deployments

set -e

DEPLOY_PATH="/opt/chatgpt-proxy"
DOCKER_USERNAME="${1:-your-username}"

echo "=== ChatGPT Proxy Server Setup ==="
echo "Deploy path: $DEPLOY_PATH"
echo "Docker username: $DOCKER_USERNAME"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo ./setup-server.sh [docker-username]"
    exit 1
fi

# Create deployment directory
echo "[1/4] Creating deployment directory..."
mkdir -p "$DEPLOY_PATH"
chown "$SUDO_USER:$SUDO_USER" "$DEPLOY_PATH"

# Create docker-compose.yml
echo "[2/4] Creating docker-compose.yml..."
cat > "$DEPLOY_PATH/docker-compose.yml" << EOF
services:
  chatgpt-proxy:
    image: ${DOCKER_USERNAME}/chatgpt-proxy:\${IMAGE_TAG:-latest}
    container_name: chatgpt-proxy
    restart: unless-stopped
    ports:
      - "8333:8333"
    env_file:
      - .env
    environment:
      - RAG_ENABLED=false
      - APP_HOST=0.0.0.0
      - APP_PORT=8333
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8333/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

# Create .env template
echo "[3/4] Creating .env template..."
if [ ! -f "$DEPLOY_PATH/.env" ]; then
    cat > "$DEPLOY_PATH/.env" << 'EOF'
# Required: OpenAI API Key
OPENAI_API_KEY=sk-your-key-here

# Optional: Model configuration
OPENAI_MODEL=gpt-4o-mini

# RAG is disabled in production by default
RAG_ENABLED=false
EOF
    chmod 600 "$DEPLOY_PATH/.env"
    chown "$SUDO_USER:$SUDO_USER" "$DEPLOY_PATH/.env"
    echo "   Created .env template - EDIT IT with your actual API key!"
else
    echo "   .env already exists, skipping..."
fi

# Set permissions
echo "[4/4] Setting permissions..."
chown -R "$SUDO_USER:$SUDO_USER" "$DEPLOY_PATH"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit $DEPLOY_PATH/.env with your OPENAI_API_KEY"
echo "2. Add GitHub Secrets in your repository:"
echo "   - DOCKER_USERNAME: $DOCKER_USERNAME"
echo "   - DOCKER_PASSWORD: Your Docker Hub access token"
echo "   - DEPLOY_HOST: $(hostname -I | awk '{print $1}')"
echo "   - DEPLOY_USER: $SUDO_USER"
echo "   - DEPLOY_KEY: Your SSH private key"
echo ""
echo "3. Push to main branch to trigger deployment!"
