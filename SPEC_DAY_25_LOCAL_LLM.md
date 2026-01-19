# Specification: Local LLM Integration (Day 25)

## Overview

Integration of local LLM inference via Ollama into the existing ChatGPT proxy application, providing an alternative to cloud-based OpenAI API with full feature parity.

## Motivation & Goals

| Goal | Description |
|------|-------------|
| **Privacy/Data Sovereignty** | Keep sensitive data off third-party servers |
| **Cost Optimization** | Eliminate per-token API costs for high-volume usage |
| **Offline Capability** | Full functionality without internet connection |
| **Experimentation** | Test different models, parameters, and configurations |

## Technical Environment

### Hardware Target
- **Platform**: Apple Silicon Mac (M4 series)
- **Unified Memory**: 24GB
- **Model Capacity**: Up to 14B parameters at Q6_K quantization

### Runtime Choice
- **Ollama** (consistent across local development and server deployment)
- Provides OpenAI-compatible API at `http://localhost:11434/v1`
- Handles model loading, quantization, and Metal acceleration

### Target Model
- **Primary**: Qwen 2.5 14B (or 7B for faster inference)
- **Quantization**: Q6_K (quality-focused, ~12GB memory)
- **Capabilities**: General chat/instruction following

## Architecture

### Integration Approach
- Drop-in OpenAI-compatible backend via Ollama's `/v1/chat/completions` endpoint
- Minimal changes to existing `chatgpt_client.py` - abstract provider selection
- Same SSE streaming format as current implementation

### Request Flow (Local Model)
```
POST /api/chat/stream
  → detect provider (local/cloud)
  → [Optional RAG retrieval]
  → [Optional MCP tools]
  → Ollama API (localhost:11434)
  → SSE events (chunk/done/error)
```

### System Components

```
┌──────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
├──────────────────────────────────────────────────────────────┤
│  Settings Panel         │  Chat Interface                    │
│  ├─ Model selector      │  ├─ Prominent Local/Cloud badge   │
│  ├─ Provider toggle     │  ├─ Stop button                   │
│  ├─ RAG toggle          │  ├─ Metrics display               │
│  └─ Advanced params     │  └─ Offline mode banner           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                       │
├──────────────────────────────────────────────────────────────┤
│  Provider Abstraction Layer                                  │
│  ├─ OpenAI Client (existing)                                │
│  └─ Ollama Client (new)                                     │
│                                                              │
│  Shared Services                                             │
│  ├─ RAG (Chunkenizer) ─────── toggleable per model          │
│  ├─ MCP Tools ─────────────── full support for local        │
│  ├─ History Summarizer ─────── same model summarizes        │
│  └─ Response Cache ─────────── persistent to disk           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    Ollama (localhost:11434)                  │
│  ├─ Qwen 2.5 14B Q6_K                                       │
│  └─ Auto-detected prompt template                           │
└──────────────────────────────────────────────────────────────┘
```

## Feature Specification

### 1. Model Selection

**Per-Conversation Selection**
- User selects model at conversation start
- Selection persists for entire conversation
- Can switch mid-conversation (history transfers)
- Future: smart routing based on query complexity

**UI Implementation**
- Dropdown/toggle at top of chat interface
- Shows available models (fetched from Ollama on startup)
- Disabled options shown grayed out if unavailable

### 2. Provider Indicator (UX)

**Prominent Badge**
- Clear visual indicator: "🖥️ Local" vs "☁️ Cloud"
- Displayed in chat header
- Different accent color for each provider

**Offline Mode Banner**
- Explicit "⚡ Offline Mode" banner when no internet detected
- Cloud features grayed out
- Auto-detect connectivity state

### 3. Streaming

**Required**: Token-by-token streaming matching current SSE implementation

```typescript
// SSE event format (unchanged)
event: chunk
data: {"delta": "partial text..."}

event: done
data: {StructuredResponse with metadata.model: "qwen2.5:14b"}
```

### 4. RAG Integration

**Toggleable Per Model**
- Setting in UI: "Enable RAG for local model"
- Default: enabled (same behavior as cloud)
- Stored in localStorage with other settings

**Implementation**
- Same `inject_rag_context()` pipeline
- Same Chunkenizer integration
- Context size may need adjustment for smaller context windows

### 5. MCP Tool Support

**Full Parity with Cloud**
- All builtin tools: filesystem, fetch, git
- External MCP servers via config
- Same tool calling format

**Consideration**
- Qwen 2.5 has good tool calling support
- Test reliability before shipping
- Fall back gracefully if tool call parsing fails

### 6. History Summarization

**Trigger**: When conversation exceeds model's context limit (32K for Qwen 2.5)

**Summarizer**: Same local model performs summarization

```python
# Pseudo-implementation
if token_count(messages) > context_limit * 0.9:
    summary = await ollama_summarize(messages[:-recent_count])
    messages = [system_prompt, summary_message, *messages[-recent_count:]]
```

**Behavior**
- Keep recent N messages intact
- Summarize older history into single context message
- Seamless to user (no explicit notification)

### 7. Metrics Display

**Detailed Metrics Panel**
- Tokens per second (inference speed)
- Memory consumption (if available from Ollama)
- Context utilization (tokens used / max tokens)
- Response time (first token, total)

**UI Location**
- Collapsible panel below chat input
- Or inline below each response

### 8. Response Caching

**Persistent Cache**
- Cache identical queries to disk
- Key: hash(model + messages + parameters)
- Invalidate on model change or explicit clear

**Storage**
- SQLite or JSON file in app data directory
- Configurable max cache size

### 9. Concurrency Handling

**UI Blocking**
- Disable send button while generating
- Show spinner/loading state
- Enable stop button

### 10. Stop/Cancel Button

**Implementation**
- Visible during generation
- Immediate cancel via Ollama API
- Show partial response generated so far

```typescript
// Frontend
const [isGenerating, setIsGenerating] = useState(false);
const abortController = useRef<AbortController>();

const handleStop = () => {
  abortController.current?.abort();
  setIsGenerating(false);
};
```

### 11. Advanced Parameter Controls

**Exposed Parameters**
| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Temperature | 0.0 - 2.0 | 0.7 | Randomness |
| Top P | 0.0 - 1.0 | 0.9 | Nucleus sampling |
| Max Tokens | 100 - 4096 | 2048 | Response length limit |

**UI**
- Collapsible "Advanced Settings" section
- Sliders with numeric input
- "Reset to Defaults" button

### 12. System Prompt

**Same as Cloud**
- Use identical Russian system prompt
- Same `/review` and `/help` special prompts
- Injected via existing `_prepare_messages()` logic

### 13. Error Handling

**Ollama Not Available**
```
┌─────────────────────────────────────────┐
│  ⚠️ Local Model Unavailable             │
│                                         │
│  Ollama is not running or the model    │
│  is not loaded.                         │
│                                         │
│  [Retry]  [Switch to Cloud]  [Help]    │
└─────────────────────────────────────────┘
```

**Actions**
- Retry: Re-check Ollama availability
- Switch to Cloud: Change provider setting
- Help: Link to README setup instructions

### 14. Health Check

**On App Startup**
1. Check if Ollama is running (`GET /api/tags`)
2. Check if target model is available
3. Update UI state accordingly

```python
async def check_ollama_health() -> OllamaStatus:
    try:
        response = await client.get("http://localhost:11434/api/tags")
        models = response.json()["models"]
        return OllamaStatus(
            available=True,
            models=[m["name"] for m in models]
        )
    except:
        return OllamaStatus(available=False, models=[])
```

### 15. Model Management

**List Only**
- Display available models from Ollama
- No pull/delete functionality in app
- Direct users to `ollama pull <model>` for new models

### 16. Per-Message Model Metadata

**In Conversation State**
```typescript
interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  model?: string;        // "qwen2.5:14b" or "gpt-4o-mini"
  provider?: "local" | "cloud";
  timestamp: number;
}
```

**Export Format**
- Include model info in JSON export
- Show in conversation review/history

### 17. History Transfer

**On Provider Switch**
- Keep full conversation history
- New messages use new provider
- Previous messages retain original model metadata

## Configuration

### Environment Variables

```bash
# Ollama Configuration
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:14b

# Can be overridden in UI settings
```

### Frontend Settings (localStorage)

```typescript
interface LocalModelSettings {
  enabled: boolean;
  model: string;
  ragEnabled: boolean;
  temperature: number;
  topP: number;
  maxTokens: number;
}
```

## Security

### Network Isolation
- Ollama connections strictly to `localhost:11434`
- No remote Ollama endpoints supported
- Prevents accidental data leakage to external servers

### File System
- MCP filesystem tools constrained to `WORKSPACE_ROOT`
- Same security model as cloud provider

## Deployment

### Local Development
- Ollama installed via `brew install ollama`
- Model pulled: `ollama pull qwen2.5:14b`
- Started: `ollama serve`

### Server (69.62.64.218)
- Ollama installed on server
- Runs alongside Docker containers
- Same configuration as local

### Docker Considerations
- Ollama runs on host (not in container)
- Container accesses host's Ollama via `host.docker.internal:11434`
- Or run Ollama in separate container with shared network

## Testing Strategy

### Unit Tests with Mocked Ollama

```python
# tests/test_ollama_client.py
@pytest.fixture
def mock_ollama():
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "http://localhost:11434/v1/chat/completions",
            json={"choices": [{"message": {"content": "Test response"}}]}
        )
        yield rsps

async def test_ollama_chat(mock_ollama):
    client = OllamaClient()
    response = await client.chat([{"role": "user", "content": "Hello"}])
    assert response.content == "Test response"
```

### Test Coverage
- Provider switching
- Streaming responses
- Error handling (Ollama unavailable)
- RAG integration with local model
- MCP tool calling
- History summarization trigger
- Cache hit/miss
- Cancel/stop functionality

## Risks & Mitigations

### 1. Response Quality Gap
**Risk**: Local model answers significantly worse than GPT-4
**Mitigations**:
- Use high-quality quantization (Q6_K)
- Test extensively before launch
- Clear indicator that local model is in use
- Easy switch to cloud if needed

### 2. Breaking Existing Features
**Risk**: Integration destabilizes current cloud functionality
**Mitigations**:
- Abstract provider selection, don't modify existing code paths
- Comprehensive test coverage
- Feature flag to disable local model entirely
- Staged rollout

### 3. Resource Consumption
**Risk**: Local model uses excessive memory/CPU
**Mitigations**:
- Display resource metrics
- Warn if model too large for available memory
- Recommend appropriate model sizes

## File Changes Required

### Backend
| File | Changes |
|------|---------|
| `app/app/config.py` | Add Ollama settings |
| `app/app/services/ollama_client.py` | **New** - Ollama API client |
| `app/app/services/provider_router.py` | **New** - Route to OpenAI or Ollama |
| `app/app/services/chatgpt_client.py` | Refactor to use provider router |
| `app/app/services/cache.py` | **New** - Response caching |
| `app/app/services/summarizer.py` | **New** - History summarization |
| `app/app/main.py` | Add health check endpoint |
| `app/app/schemas.py` | Add model metadata to responses |

### Frontend
| File | Changes |
|------|---------|
| `src/store/settingsStore.ts` | Add local model settings |
| `src/services/api.ts` | Add Ollama health check |
| `src/components/Settings/LocalModelSettings.tsx` | **New** |
| `src/components/Chat/ProviderBadge.tsx` | **New** |
| `src/components/Chat/StopButton.tsx` | **New** |
| `src/components/Chat/MetricsPanel.tsx` | **New** |
| `src/components/Chat/OfflineBanner.tsx` | **New** |

### Documentation
| File | Changes |
|------|---------|
| `README.md` | Add Ollama setup instructions |

## API Endpoints

### New Endpoints

```
GET /api/ollama/health
  → { available: bool, models: string[] }

GET /api/ollama/models
  → { models: [{ name, size, quantization }] }

POST /api/chat/cancel
  → { success: bool }
```

### Modified Endpoints

```
POST /api/chat
  + body.provider: "local" | "cloud"
  + body.model: string (optional override)
  + response.metadata.model: string
  + response.metadata.provider: string

POST /api/chat/stream
  + same additions as /api/chat
```

## Success Criteria

1. ✅ Ollama installed and running locally
2. ✅ Qwen 2.5 model loaded and responding
3. ✅ Chat works via local model with streaming
4. ✅ Clear UI indicator of active provider
5. ✅ RAG toggle works for local model
6. ✅ MCP tools work with local model
7. ✅ History summarization triggers at context limit
8. ✅ Metrics displayed during inference
9. ✅ Stop button cancels generation
10. ✅ Persistent caching reduces repeated queries
11. ✅ Offline mode detected and indicated
12. ✅ Error handling for Ollama unavailability
13. ✅ Unit tests pass with mocked Ollama
14. ✅ Works on server deployment

---

*Specification generated from interview on Day 25*
*Full feature set requested, no tradeoffs*
