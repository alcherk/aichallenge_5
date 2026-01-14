# Frequently Asked Questions (FAQ)

## Table of Contents

- [General Questions](#general-questions)
- [Installation Issues](#installation-issues)
- [Configuration](#configuration)
- [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
- [Assistant Mode](#assistant-mode)
- [Developer Assistant Mode](#developer-assistant-mode)
- [MCP (Model Context Protocol)](#mcp-model-context-protocol)
- [Frontend Issues](#frontend-issues)
- [Backend Issues](#backend-issues)
- [Troubleshooting](#troubleshooting)

---

## General Questions

### What is this project?

This is a ChatGPT Proxy Service - a modern FastAPI-based proxy service with a React + TypeScript frontend that forwards requests to the ChatGPT API. It includes advanced features like RAG (Retrieval-Augmented Generation), MCP tool integration, and developer assistant capabilities.

### What are the main features?

- **Chat Interface**: Real-time chat with streaming responses
- **RAG Integration**: Document retrieval and context injection for enhanced responses
- **Assistant Mode**: Strict RAG-only mode for FAQ/documentation systems
- **Developer Assistant Mode**: Automatic project documentation and Git context integration
- **MCP Tools**: Integration with external tools via Model Context Protocol
- **Metrics Tracking**: Token usage, cost calculation, and performance monitoring
- **Settings Management**: Model selection, temperature control, custom system prompts

### What technologies are used?

**Backend:**
- Python 3.11
- FastAPI
- Uvicorn
- httpx (async HTTP client)
- Pydantic (data validation)

**Frontend:**
- React 18
- TypeScript
- Vite (build tool)
- Tailwind CSS v4
- Zustand (state management)
- React Markdown

---

## Installation Issues

### How do I install the project?

**Development Setup:**

1. **Backend:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   export OPENAI_API_KEY="your-key-here"
   uvicorn app.app.main:app --reload --port 8333
   ```

2. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Chunkenizer (for RAG):**
   ```bash
   cd ../Chunkenizer
   docker-compose up -d
   ```

### I'm getting "ModuleNotFoundError" when running the backend

**Solution:**
- Make sure you've activated the virtual environment: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Check that you're running from the project root directory
- Verify Python version: `python --version` (should be 3.11+)

### npm install fails with errors

**Common issues:**
- **Node version**: Ensure you're using Node.js 18+ (`node --version`)
- **Network issues**: Try `npm install --legacy-peer-deps`
- **Permission errors**: On Linux/Mac, avoid using `sudo`. Fix npm permissions instead
- **Cache issues**: Clear npm cache: `npm cache clean --force`

### Docker build fails

**Solutions:**
- Ensure Docker is running: `docker ps`
- Check Docker version: `docker --version` (should be 20.10+)
- Try rebuilding without cache: `docker build --no-cache -t chatgpt-proxy .`
- Check available disk space: `docker system df`
- Verify Dockerfile syntax and paths

### Port 8333 is already in use

**Solution:**
- Find the process using the port:
  ```bash
  # Linux/Mac
  lsof -i :8333
  # Windows
  netstat -ano | findstr :8333
  ```
- Kill the process or change the port:
  ```bash
  export APP_PORT=8334
  uvicorn app.app.main:app --reload --port 8334
  ```

### Python virtual environment activation doesn't work

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

If it still doesn't work, recreate the venv:
```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

### Where do I set the OpenAI API key?

**Option 1: Environment variable (recommended)**
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Option 2: Docker**
```bash
docker run -e OPENAI_API_KEY="sk-your-key-here" ...
```

**Option 3: .env file (if supported)**
Create a `.env` file in the project root:
```
OPENAI_API_KEY=sk-your-key-here
```

### How do I change the default model?

Set the `OPENAI_MODEL` environment variable:
```bash
export OPENAI_MODEL="gpt-4o"
```

Available models:
- `gpt-4o` (recommended)
- `gpt-4-turbo`
- `gpt-4`
- `gpt-4o-mini` (default, cost-effective)
- `gpt-3.5-turbo`

### How do I configure RAG?

See [RAG Configuration](#rag-retrieval-augmented-generation) section below.

### How do I enable MCP tools?

1. Create `mcp_servers.json` (start from `mcp_servers.example.json`)
2. Set environment variables:
   ```bash
   export MCP_CONFIG_PATH="/absolute/path/to/mcp_servers.json"
   export WORKSPACE_ROOT="/absolute/path/to/your/workspace"
   ```
3. Restart the backend

### Settings are not persisting

**Frontend settings:**
- Settings are stored in browser `localStorage`
- Clear browser cache/data to reset
- Check browser console for errors
- Ensure cookies/localStorage are enabled

**Backend settings:**
- Backend settings come from environment variables
- Changes require backend restart
- Check logs for configuration errors

---

## RAG (Retrieval-Augmented Generation)

### What is RAG and why do I need it?

RAG enhances chat responses by retrieving relevant document chunks from Chunkenizer before generating answers. This allows the assistant to:
- Answer questions based on your specific documents
- Provide citations to sources
- Use up-to-date information from your knowledge base

### How do I set up Chunkenizer?

1. **Start Chunkenizer:**
   ```bash
   cd ../Chunkenizer
   docker-compose up -d
   ```

2. **Verify it's running:**
   ```bash
   curl http://localhost:8000/api/health
   # Should return: {"status":"ok"}
   ```

3. **Check status:**
   ```bash
   python scripts/check_chunkenizer.py
   # Or
   ./scripts/check_chunkenizer.sh
   ```

### Chunkenizer connection fails

**Symptoms:**
- "Connection refused" errors
- RAG not working
- "All connection attempts failed" in logs

**Solutions:**
1. **Check if Chunkenizer is running:**
   ```bash
   curl http://localhost:8000/api/health
   ```

2. **Verify port:**
   - Default: `8000`
   - Check `CHUNKENIZER_API_URL` environment variable
   - Ensure no firewall blocking the port

3. **Docker issues:**
   ```bash
   docker ps  # Check if container is running
   docker logs <container-name>  # Check logs
   docker-compose restart  # Restart if needed
   ```

4. **Network connectivity:**
   - If running in Docker, ensure containers can communicate
   - Check Docker network configuration

### How do I upload documents to Chunkenizer?

**Option 1: API**
```bash
curl -X POST http://localhost:8000/documents \
  -F "file=@document.txt" \
  -F "metadata_json={\"source\": \"docs\"}"
```

**Option 2: Web UI**
Open `http://localhost:8000` in your browser

**Option 3: Script**
```bash
python scripts/ingest_project_docs.py --chunkenizer-url http://localhost:8000
```

### RAG is not retrieving relevant chunks

**Possible causes:**
1. **No documents indexed**: Upload documents to Chunkenizer first
2. **Low similarity threshold**: Adjust `RAG_MIN_SIMILARITY` (try 0.3-0.7)
3. **Query too specific**: Try broader queries
4. **Chunkenizer not running**: Check Chunkenizer status

**Debug steps:**
1. Check backend logs for RAG retrieval details
2. Verify documents are indexed: Check Chunkenizer UI
3. Test Chunkenizer search directly:
   ```bash
   curl -X POST http://localhost:8000/search \
     -H "Content-Type: application/json" \
     -d '{"query": "your query", "top_k": 5}'
   ```

### How do I disable RAG?

Set environment variable:
```bash
export RAG_ENABLED=false
```

Or in the UI: RAG will be automatically disabled if Chunkenizer is not accessible.

### RAG responses are too long or include irrelevant information

**Solutions:**
1. **Adjust top_k**: Reduce `RAG_TOP_K` (default: 5)
   ```bash
   export RAG_TOP_K=3
   ```

2. **Set similarity threshold**: Filter low-quality chunks
   ```bash
   export RAG_MIN_SIMILARITY=0.5
   ```

3. **Limit context size**: Reduce `RAG_MAX_CONTEXT_CHARS`
   ```bash
   export RAG_MAX_CONTEXT_CHARS=4000
   ```

### Citations are not showing

**Check:**
1. RAG is enabled: `RAG_ENABLED=true`
2. Documents are indexed in Chunkenizer
3. Chunks are being retrieved (check logs)
4. System prompt includes citation instructions

**Format:** Citations appear as `[doc_name:doc_id:chunk_index]`

---

## Assistant Mode

### What is Assistant Mode?

Assistant Mode is a strict RAG-only mode that:
- Only answers using information from RAG documents
- Responds "I don't have that information" if no relevant info found
- Does not use general knowledge or make assumptions
- Works independently of `RAG_ENABLED` setting

### How do I enable Assistant Mode?

1. Open Settings panel (gear icon in UI)
2. Toggle "Assistant Mode" switch
3. Save settings

### Assistant Mode always says "I don't have that information"

**Causes:**
1. **No documents indexed**: Upload documents to Chunkenizer
2. **Query doesn't match documents**: Try different wording
3. **Chunkenizer not running**: Check Chunkenizer status
4. **Documents not relevant**: Ensure your documents contain the information

**Solutions:**
1. Verify documents are indexed in Chunkenizer
2. Check backend logs for RAG retrieval
3. Test query directly in Chunkenizer search
4. Ensure Assistant Mode is actually enabled (check UI)

### Can I use Assistant Mode with Developer Assistant Mode?

No. When Assistant Mode is enabled, Developer Assistant Mode features (Git context, `/help`, `/review` commands) are disabled for that request. They are separate modes.

### Assistant Mode is not working

**Checklist:**
1. ✅ Assistant Mode toggle is ON in Settings
2. ✅ Settings are saved
3. ✅ Chunkenizer is running
4. ✅ Documents are indexed
5. ✅ Backend logs show RAG retrieval attempts

**Debug:**
- Check browser console for errors
- Check backend logs for "Assistant Mode enabled" messages
- Verify `assistant_mode` is included in API requests

---

## Developer Assistant Mode

### What is Developer Assistant Mode?

Developer Assistant Mode automatically:
- Detects project-related questions
- Uses RAG with project documentation
- Includes Git context (branch, modified files)
- Provides `/help` and `/review` commands

### How do I enable Developer Assistant Mode?

It's enabled by default. To disable:
```bash
export DEV_ASSISTANT_MODE=false
```

### `/help` command is not working

**Checklist:**
1. ✅ Developer Assistant Mode is enabled
2. ✅ Chunkenizer is running
3. ✅ Project documentation is indexed
4. ✅ You're in a Git repository (for Git context)

**Debug:**
- Check backend logs for `/help` command detection
- Verify RAG retrieval is happening
- Test with: `/help how is chat implemented`

### `/review` command times out or gets stuck

**Causes:**
1. **Large diff**: Increase `GIT_MCP_MAX_DIFF_SIZE`
   ```bash
   export GIT_MCP_MAX_DIFF_SIZE=500K  # or 1M
   ```

2. **Git MCP server issues**: Check logs for MCP errors
3. **No changes to review**: Ensure you have uncommitted changes

**Solutions:**
1. Increase diff size limit (see above)
2. Review smaller commits: `/review HEAD~1` instead of `/review`
3. Check Git MCP server logs
4. Ensure Git repository is initialized

### `/review` shows "I don't have enough context"

**Causes:**
1. No uncommitted changes
2. Git MCP server not working
3. No changes in the specified commit

**Solutions:**
1. Make some changes to files
2. Check Git status: `git status`
3. Try specific commit: `/review commit` or `/review HEAD~1`
4. Check MCP manager logs

### Auto-indexing script is not working

**Common issues:**
1. **Git not initialized**: Run `git init`
2. **No files to index**: Ensure files match patterns (`.py`, `.ts`, `.md`, etc.)
3. **Chunkenizer not running**: Check Chunkenizer status
4. **Permission errors**: Check file permissions

**Debug:**
```bash
# Run with verbose output
python scripts/auto_index_project.py --full-scan --repo-path . -v

# Check state file
cat .rag_index_state.json
```

### Project questions are not detected automatically

**Check:**
1. Developer Assistant Mode is enabled
2. Project documentation is indexed
3. Question is actually project-related (mentions code, files, architecture)

**Try:**
- Use `/help` command for explicit project questions
- Be more specific: "How does RAG work in this project?" vs "What is RAG?"

---

## MCP (Model Context Protocol)

### What is MCP?

MCP (Model Context Protocol) allows the assistant to use external tools at runtime. The project includes builtin servers for filesystem, fetch, and Git operations.

### How do I configure MCP servers?

1. Create `mcp_servers.json`:
   ```json
   {
     "servers": [
       {
         "name": "my-server",
         "transport": "stdio",
         "command": ["python", "-m", "my_mcp_server"]
       }
     ]
   }
   ```

2. Set environment variables:
   ```bash
   export MCP_CONFIG_PATH="/path/to/mcp_servers.json"
   export WORKSPACE_ROOT="/path/to/workspace"
   ```

3. Restart backend

### MCP tools are not available

**Checklist:**
1. ✅ `MCP_CONFIG_PATH` is set correctly
2. ✅ Config file is valid JSON
3. ✅ MCP servers are accessible
4. ✅ Backend logs show MCP initialization

**Debug:**
- Check backend logs for MCP errors
- Verify config file syntax
- Test MCP server manually
- Check file permissions

### Git MCP tools not found

**Solution:**
The builtin Git server should be automatically loaded. If not:
1. Check backend logs for MCP manager initialization
2. Verify `workspace_root` is set to a Git repository
3. Ensure Git is installed: `git --version`
4. Check MCP manager logs

### MCP server crashes with large responses

**Solution:**
For Git MCP server, increase diff size limit:
```bash
export GIT_MCP_MAX_DIFF_SIZE=1M  # or 500K
```

Maximum: 10MB

---

## Frontend Issues

### Frontend doesn't load

**Check:**
1. Backend is running on port 8333
2. No CORS errors in browser console
3. Frontend build exists: `frontend/dist/index.html`

**Development:**
- Ensure Vite dev server is running: `npm run dev`
- Check Vite is proxying to backend correctly

**Production:**
- Rebuild frontend: `cd frontend && npm run build`
- Check `frontend/dist/` exists

### Settings are not saving

**Solutions:**
1. Check browser console for errors
2. Ensure localStorage is enabled
3. Clear browser cache and try again
4. Check browser storage quota

### Messages are not persisting

**Check:**
1. Browser localStorage is enabled
2. No storage quota exceeded
3. Browser console for errors
4. Try clearing and re-adding messages

### Streaming is not working

**Check:**
1. Backend supports SSE: Check `/api/chat/stream` endpoint
2. Network tab shows `text/event-stream` responses
3. No CORS issues
4. Browser supports SSE (all modern browsers do)

### UI looks broken or styles are missing

**Solutions:**
1. Rebuild frontend: `cd frontend && npm run build`
2. Clear browser cache
3. Check Tailwind CSS is configured correctly
4. Verify `frontend/dist/assets/` contains CSS files

### TypeScript errors in frontend

**Solutions:**
1. Install dependencies: `npm install`
2. Check TypeScript version: `npx tsc --version`
3. Clear node_modules and reinstall:
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

---

## Backend Issues

### Backend won't start

**Common errors:**
1. **Port already in use**: Change port or kill existing process
2. **Missing dependencies**: `pip install -r requirements.txt`
3. **Python version**: Ensure Python 3.11+
4. **API key missing**: Set `OPENAI_API_KEY`

**Debug:**
```bash
# Check what's using the port
lsof -i :8333

# Check Python version
python --version

# Check dependencies
pip list

# Run with verbose logging
uvicorn app.app.main:app --reload --log-level debug
```

### API requests are failing

**Check:**
1. OpenAI API key is valid
2. Network connectivity
3. API rate limits
4. Request format is correct

**Debug:**
- Check backend logs
- Test API key: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
- Verify request format matches schema

### Health endpoint returns error

**Check:**
```bash
curl http://localhost:8333/health
```

Should return: `{"status":"ok"}`

If not:
1. Backend might not be running
2. Port might be wrong
3. Check backend logs

### CORS errors in browser

**Development:**
- CORS should be enabled by default
- Check backend CORS configuration
- Verify frontend is calling correct backend URL

**Production:**
- Configure CORS origins properly
- Use reverse proxy (nginx) for same-origin requests

### Logs are too verbose or not showing

**Adjust log level:**
```bash
export LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

---

## Troubleshooting

### General troubleshooting steps

1. **Check logs:**
   - Backend: `docker logs chatgpt-proxy` or terminal output
   - Frontend: Browser console (F12)
   - Chunkenizer: `docker logs <chunkenizer-container>`

2. **Verify services:**
   ```bash
   # Backend
   curl http://localhost:8333/health
   
   # Chunkenizer
   curl http://localhost:8000/api/health
   ```

3. **Check environment variables:**
   ```bash
   env | grep -E "(OPENAI|RAG|MCP|CHUNKENIZER)"
   ```

4. **Test components individually:**
   - Test Chunkenizer search directly
   - Test backend API with curl
   - Test frontend in isolation

### Common error messages

**"OPENAI_API_KEY is not configured"**
- Set `OPENAI_API_KEY` environment variable

**"Connection refused" (Chunkenizer)**
- Start Chunkenizer: `docker-compose up -d` in Chunkenizer directory
- Check Chunkenizer is running: `curl http://localhost:8000/api/health`

**"MCP stdio request timeout"**
- Increase timeout in MCP transport
- Check MCP server is responding
- Reduce request size (e.g., smaller git diff)

**"No chunks retrieved"**
- Verify documents are indexed in Chunkenizer
- Check query relevance
- Lower `RAG_MIN_SIMILARITY` threshold

**"Module not found"**
- Activate virtual environment
- Install dependencies: `pip install -r requirements.txt`

### Getting help

1. **Check documentation:**
   - [README.md](README.md) - Main documentation
   - [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
   - [CONTEXT.md](CONTEXT.md) - Architectural notes

2. **Check logs:**
   - Backend logs show detailed error information
   - Frontend console shows client-side errors

3. **Verify setup:**
   - All services are running
   - Environment variables are set
   - Dependencies are installed

4. **Test components:**
   - Test each component independently
   - Use health endpoints
   - Check service connectivity

---

## Still having issues?

If you've tried the solutions above and still have problems:

1. **Collect information:**
   - Error messages (full text)
   - Backend logs
   - Frontend console errors
   - Environment details (OS, Python version, Node version)
   - Steps to reproduce

2. **Check for updates:**
   - Update dependencies
   - Check for known issues
   - Review recent changes

3. **Isolate the problem:**
   - Test with minimal configuration
   - Disable optional features (RAG, MCP)
   - Test with default settings

4. **Review configuration:**
   - Verify all environment variables
   - Check config files are valid
   - Ensure paths are correct

---

*Last updated: Based on current project state*
