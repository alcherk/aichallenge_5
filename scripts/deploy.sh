#!/bin/bash
# Manual deploy script for ChatGPT Proxy
# Usage: ./scripts/deploy.sh

set -e

SERVER="root@69.62.64.218"
REMOTE_PATH="/root/aichallenge_5"

echo "=== ChatGPT Proxy Deploy ==="
echo ""

# Step 1: Git push
echo "[1/4] Pushing changes to git..."
git add -A
if git diff --cached --quiet; then
    echo "   No changes to commit, pushing existing commits..."
else
    git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M:%S')"
fi
git push origin main

# Step 2-4: SSH to server and deploy
echo "[2/4] Connecting to server..."
echo "[3/4] Pulling changes and rebuilding..."
echo "[4/4] Restarting container..."

ssh "$SERVER" << 'ENDSSH'
set -e
cd /root/aichallenge_5

echo "   Pulling latest changes..."
git pull origin main

echo "   Rebuilding Docker image..."
docker compose build

echo "   Restarting container..."
docker compose up -d --force-recreate

echo "   Waiting for health check..."
sleep 5

if curl -sf http://localhost:8333/health > /dev/null 2>&1; then
    echo "   Health check PASSED"
else
    echo "   Health check FAILED"
    docker compose logs --tail=20
    exit 1
fi
ENDSSH

echo ""
echo "=== Deploy Complete ==="
