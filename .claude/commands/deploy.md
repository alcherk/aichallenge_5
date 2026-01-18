# Deploy to Production

Execute the full deployment pipeline for ChatGPT Proxy.

## Steps

1. **Git**: Add all changes, commit (if any), and push to `main`
2. **SSH**: Connect to `root@69.62.64.218`
3. **Pull**: `cd /root/aichallenge_5 && git pull origin main`
4. **Build**: `docker compose build`
5. **Restart**: `docker compose up -d --force-recreate`
6. **Health check**: Verify `http://localhost:8333/health` responds

## Execution

Run these commands in sequence:

```bash
# 1. Git push
git add -A
git diff --cached --quiet || git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main

# 2-5. SSH deploy
ssh root@69.62.64.218 << 'EOF'
cd /root/aichallenge_5
git pull origin main
docker compose build
docker compose up -d --force-recreate
sleep 5
curl -sf http://localhost:8333/health && echo " - Health OK"
EOF
```

Report the deployment status when complete.
