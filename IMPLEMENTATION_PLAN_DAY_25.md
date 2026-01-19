# Implementation Plan: Local LLM Integration

## Overview

This plan is structured for **3-4 parallel developers** working simultaneously. Tasks are organized into phases with clear dependencies.

```
Legend:
  🔒 SEQUENTIAL - Must be done in order, blocks other work
  🔀 PARALLEL   - Can be done simultaneously with other parallel tasks
  ⏳ BLOCKED BY - Cannot start until specified task completes
```

---

## Phase 0: Foundation (🔒 SEQUENTIAL)

> **CRITICAL**: This phase MUST be completed before any parallel work begins.
> All subsequent phases depend on these foundational components.

### Task 0.1: Backend Configuration
**Developer**: Backend Lead
**Estimate**: Core infrastructure

**Files to create/modify**:
- `app/app/config.py`

**Implementation**:
```python
# Add to Settings class
class Settings(BaseSettings):
    # ... existing settings ...

    # Ollama Configuration
    ollama_enabled: bool = Field(default=True, env="OLLAMA_ENABLED")
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_default_model: str = Field(default="qwen2.5:14b", env="OLLAMA_DEFAULT_MODEL")
    ollama_timeout: int = Field(default=120, env="OLLAMA_TIMEOUT")
```

**Acceptance criteria**:
- [ ] Settings load from environment
- [ ] Defaults work without env vars
- [ ] Settings accessible via `get_settings()`

---

### Task 0.2: Ollama Client
**Developer**: Backend Lead
**Estimate**: Core infrastructure
**⏳ BLOCKED BY**: Task 0.1

**Files to create**:
- `app/app/services/ollama_client.py`

**Implementation**:
```python
class OllamaClient:
    """OpenAI-compatible client for Ollama."""

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
    ) -> OllamaResponse: ...

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        **kwargs
    ) -> AsyncGenerator[str, None]: ...

    async def health_check(self) -> OllamaStatus: ...

    async def list_models(self) -> list[OllamaModel]: ...

    async def cancel(self) -> bool: ...
```

**Acceptance criteria**:
- [ ] Non-streaming chat works
- [ ] Streaming chat yields tokens
- [ ] Health check returns status
- [ ] Model list returns available models
- [ ] Timeout handling works

---

### Task 0.3: Provider Router
**Developer**: Backend Lead
**Estimate**: Core infrastructure
**⏳ BLOCKED BY**: Task 0.2

**Files to create**:
- `app/app/services/provider_router.py`

**Files to modify**:
- `app/app/services/chatgpt_client.py` (minimal changes)

**Implementation**:
```python
class ProviderRouter:
    """Routes requests to appropriate LLM provider."""

    def __init__(self):
        self.openai_client = OpenAIClient()
        self.ollama_client = OllamaClient()

    async def chat(
        self,
        messages: list[dict],
        provider: Literal["cloud", "local"] = "cloud",
        **kwargs
    ) -> ProviderResponse: ...

    async def stream_chat(
        self,
        messages: list[dict],
        provider: Literal["cloud", "local"] = "cloud",
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]: ...
```

**Key principle**: Existing `chatgpt_client.py` code paths remain untouched. Router wraps both providers with unified interface.

**Acceptance criteria**:
- [ ] Routes to correct provider based on param
- [ ] Unified response format from both providers
- [ ] Streaming works for both providers
- [ ] Existing cloud functionality unchanged

---

### Task 0.4: Schema Updates
**Developer**: Backend Lead
**Estimate**: Core infrastructure
**⏳ BLOCKED BY**: Task 0.3

**Files to modify**:
- `app/app/schemas.py`

**Implementation**:
```python
class ChatRequest(BaseModel):
    # ... existing fields ...
    provider: Literal["cloud", "local"] = "cloud"
    model: str | None = None  # Override default model
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None

class ChatResponse(BaseModel):
    # ... existing fields ...
    model: str | None = None
    provider: str | None = None

class MessageMetadata(BaseModel):
    model: str
    provider: Literal["cloud", "local"]
    timestamp: float
    tokens_used: int | None = None
    inference_time_ms: int | None = None
```

**Acceptance criteria**:
- [ ] Request accepts provider selection
- [ ] Response includes model metadata
- [ ] Backwards compatible with existing clients

---

### Task 0.5: Endpoint Integration
**Developer**: Backend Lead
**Estimate**: Core infrastructure
**⏳ BLOCKED BY**: Task 0.4

**Files to modify**:
- `app/app/main.py`

**Implementation**:
- Modify `/api/chat` to use `ProviderRouter`
- Modify `/api/chat/stream` to use `ProviderRouter`
- Add provider to response metadata

**Acceptance criteria**:
- [ ] `/api/chat` works with `provider: "local"`
- [ ] `/api/chat/stream` works with `provider: "local"`
- [ ] Existing cloud requests work unchanged
- [ ] Response includes model/provider metadata

---

## Phase 0 Completion Checkpoint ✅

Before proceeding to Phase 1, verify:
- [ ] `ollama serve` running locally
- [ ] `ollama pull qwen2.5:14b` completed
- [ ] `curl http://localhost:11434/api/tags` returns model list
- [ ] Basic chat via local model works end-to-end
- [ ] Streaming via local model works
- [ ] Cloud model still works (no regression)

---

## Phase 1: Parallel Feature Development (🔀 PARALLEL)

> **4 parallel work streams** can proceed simultaneously after Phase 0.

---

### Stream A: Backend Services (Developer 1)

#### Task A.1: Response Cache Service 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to create**:
- `app/app/services/cache.py`

**Implementation**:
```python
class ResponseCache:
    """Persistent response cache using SQLite."""

    def __init__(self, db_path: str = "cache/responses.db"):
        self._init_db()

    def cache_key(
        self,
        model: str,
        messages: list[dict],
        params: dict
    ) -> str:
        """Generate deterministic cache key."""
        return hashlib.sha256(
            json.dumps({"model": model, "messages": messages, **params}, sort_keys=True).encode()
        ).hexdigest()

    async def get(self, key: str) -> CachedResponse | None: ...
    async def set(self, key: str, response: str, metadata: dict) -> None: ...
    async def clear(self) -> None: ...
    async def get_stats(self) -> CacheStats: ...
```

**Acceptance criteria**:
- [ ] Cache persists across restarts
- [ ] Cache key deterministic for same input
- [ ] Cache hit returns stored response
- [ ] Cache stats available (hits, misses, size)

---

#### Task A.2: History Summarizer Service 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to create**:
- `app/app/services/summarizer.py`

**Implementation**:
```python
class HistorySummarizer:
    """Summarizes conversation history when context limit approached."""

    SUMMARIZE_PROMPT = """Summarize the following conversation concisely,
    preserving key facts, decisions, and context needed for continuation:

    {conversation}

    Summary:"""

    async def should_summarize(
        self,
        messages: list[dict],
        model: str,
        threshold: float = 0.9
    ) -> bool:
        """Check if messages exceed threshold of context limit."""
        token_count = self._count_tokens(messages)
        context_limit = self._get_context_limit(model)
        return token_count > context_limit * threshold

    async def summarize(
        self,
        messages: list[dict],
        keep_recent: int = 4,
        provider: str = "local"
    ) -> list[dict]:
        """Summarize old messages, keep recent ones intact."""
        ...
```

**Acceptance criteria**:
- [ ] Correctly detects when summarization needed
- [ ] Summarizes using same model (local stays local)
- [ ] Keeps recent N messages intact
- [ ] Summary is coherent and useful

---

#### Task A.3: Integrate Cache into Router 🔀
**⏳ BLOCKED BY**: Task A.1

**Files to modify**:
- `app/app/services/provider_router.py`

**Implementation**:
- Check cache before calling provider
- Store response in cache after generation
- Skip cache for streaming (or cache final result)

**Acceptance criteria**:
- [ ] Repeated identical queries return cached response
- [ ] Cache bypass option available
- [ ] Streaming caches final result

---

#### Task A.4: Integrate Summarizer into Router 🔀
**⏳ BLOCKED BY**: Task A.2

**Files to modify**:
- `app/app/services/provider_router.py`

**Implementation**:
- Check if summarization needed before request
- Apply summarization transparently
- Include summarization in metadata

**Acceptance criteria**:
- [ ] Long conversations automatically summarized
- [ ] User experience seamless
- [ ] Metadata indicates if summarization occurred

---

### Stream B: Frontend Core UI (Developer 2)

#### Task B.1: Settings Store Extension 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to modify**:
- `src/store/settingsStore.ts`

**Implementation**:
```typescript
interface LocalModelSettings {
  enabled: boolean;
  provider: 'cloud' | 'local';
  model: string;
  ragEnabled: boolean;
  temperature: number;
  topP: number;
  maxTokens: number;
}

interface SettingsStore {
  // ... existing ...
  localModel: LocalModelSettings;
  setLocalModelSetting: <K extends keyof LocalModelSettings>(
    key: K,
    value: LocalModelSettings[K]
  ) => void;
  resetLocalModelSettings: () => void;
}
```

**Acceptance criteria**:
- [ ] Settings persist to localStorage
- [ ] Default values sensible
- [ ] Reset to defaults works

---

#### Task B.2: Local Model Settings Panel 🔀
**⏳ BLOCKED BY**: Task B.1

**Files to create**:
- `src/components/Settings/LocalModelSettings.tsx`

**Implementation**:
```typescript
export function LocalModelSettings() {
  return (
    <div className="local-model-settings">
      <h3>Local Model</h3>

      {/* Provider Toggle */}
      <ProviderToggle />

      {/* Model Selector */}
      <ModelSelector models={availableModels} />

      {/* RAG Toggle */}
      <Toggle label="Enable RAG" ... />

      {/* Advanced Settings (collapsible) */}
      <Collapsible title="Advanced">
        <Slider label="Temperature" min={0} max={2} step={0.1} />
        <Slider label="Top P" min={0} max={1} step={0.05} />
        <Slider label="Max Tokens" min={100} max={4096} step={100} />
      </Collapsible>

      <Button onClick={resetToDefaults}>Reset to Defaults</Button>
    </div>
  );
}
```

**Acceptance criteria**:
- [ ] All settings adjustable
- [ ] Changes persist immediately
- [ ] Reset button works
- [ ] Sliders have appropriate ranges

---

#### Task B.3: Provider Badge Component 🔀
**⏳ BLOCKED BY**: Task B.1

**Files to create**:
- `src/components/Chat/ProviderBadge.tsx`

**Implementation**:
```typescript
export function ProviderBadge({ provider }: { provider: 'local' | 'cloud' }) {
  return (
    <div className={`provider-badge provider-badge--${provider}`}>
      {provider === 'local' ? (
        <>🖥️ Local</>
      ) : (
        <>☁️ Cloud</>
      )}
    </div>
  );
}
```

**Styles**:
- Local: green/teal accent
- Cloud: blue accent
- Prominent placement in chat header

**Acceptance criteria**:
- [ ] Clearly visible
- [ ] Distinct visual for each provider
- [ ] Updates when provider changes

---

#### Task B.4: Model Selector Dropdown 🔀
**⏳ BLOCKED BY**: Task B.1

**Files to create**:
- `src/components/Chat/ModelSelector.tsx`

**Implementation**:
- Dropdown showing available models
- Grouped by provider (Local / Cloud)
- Shows model status (loaded/available/unavailable)

**Acceptance criteria**:
- [ ] Shows local models from Ollama
- [ ] Shows cloud model options
- [ ] Disabled if model unavailable
- [ ] Selection persists for conversation

---

### Stream C: Frontend Advanced UI (Developer 3)

#### Task C.1: Metrics Store 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to modify**:
- `src/store/metricsStore.ts`

**Implementation**:
```typescript
interface InferenceMetrics {
  tokensPerSecond: number;
  firstTokenLatencyMs: number;
  totalLatencyMs: number;
  tokensGenerated: number;
  contextUtilization: number; // 0-1
}

interface MetricsStore {
  currentMetrics: InferenceMetrics | null;
  setMetrics: (metrics: InferenceMetrics) => void;
  clearMetrics: () => void;
}
```

**Acceptance criteria**:
- [ ] Metrics update during streaming
- [ ] Metrics cleared on new request

---

#### Task C.2: Metrics Panel Component 🔀
**⏳ BLOCKED BY**: Task C.1

**Files to create**:
- `src/components/Chat/MetricsPanel.tsx`

**Implementation**:
```typescript
export function MetricsPanel() {
  const { currentMetrics } = useMetricsStore();

  if (!currentMetrics) return null;

  return (
    <div className="metrics-panel">
      <MetricItem
        label="Speed"
        value={`${currentMetrics.tokensPerSecond.toFixed(1)} tok/s`}
      />
      <MetricItem
        label="First token"
        value={`${currentMetrics.firstTokenLatencyMs}ms`}
      />
      <MetricItem
        label="Context"
        value={`${(currentMetrics.contextUtilization * 100).toFixed(0)}%`}
      />
    </div>
  );
}
```

**Acceptance criteria**:
- [ ] Shows live metrics during generation
- [ ] Collapsible/dismissible
- [ ] Only shows for local model (optional for cloud)

---

#### Task C.3: Stop Button Component 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to create**:
- `src/components/Chat/StopButton.tsx`

**Files to modify**:
- `src/services/streaming.ts`

**Implementation**:
```typescript
export function StopButton({ onStop }: { onStop: () => void }) {
  return (
    <button
      className="stop-button"
      onClick={onStop}
      aria-label="Stop generation"
    >
      ⬛ Stop
    </button>
  );
}

// In streaming service
const abortController = new AbortController();

export function cancelGeneration() {
  abortController.abort();
}
```

**Acceptance criteria**:
- [ ] Visible only during generation
- [ ] Immediately stops streaming
- [ ] Shows partial response generated

---

#### Task C.4: Offline Banner Component 🔀
**⏳ BLOCKED BY**: Task B.1

**Files to create**:
- `src/components/Chat/OfflineBanner.tsx`
- `src/hooks/useOnlineStatus.ts`

**Implementation**:
```typescript
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
}

export function OfflineBanner() {
  const isOnline = useOnlineStatus();

  if (isOnline) return null;

  return (
    <div className="offline-banner">
      ⚡ Offline Mode — Using local model only
    </div>
  );
}
```

**Acceptance criteria**:
- [ ] Detects offline state
- [ ] Shows prominent banner
- [ ] Auto-hides when back online

---

### Stream D: Backend Integration & Health (Developer 4)

#### Task D.1: Health Check Endpoint 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to modify**:
- `app/app/main.py`

**Implementation**:
```python
@app.get("/api/ollama/health")
async def ollama_health():
    """Check Ollama availability and list models."""
    client = OllamaClient()
    status = await client.health_check()
    return {
        "available": status.available,
        "models": status.models,
        "default_model": settings.ollama_default_model,
        "default_loaded": settings.ollama_default_model in status.models
    }

@app.get("/api/ollama/models")
async def ollama_models():
    """List available Ollama models with details."""
    client = OllamaClient()
    return await client.list_models()
```

**Acceptance criteria**:
- [ ] Returns availability status
- [ ] Lists available models
- [ ] Handles Ollama not running gracefully

---

#### Task D.2: Cancel Endpoint 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to modify**:
- `app/app/main.py`

**Implementation**:
```python
# Track active generations
active_generations: dict[str, asyncio.Task] = {}

@app.post("/api/chat/cancel")
async def cancel_generation(request_id: str):
    """Cancel an in-progress generation."""
    if request_id in active_generations:
        active_generations[request_id].cancel()
        del active_generations[request_id]
        return {"success": True, "message": "Generation cancelled"}
    return {"success": False, "message": "No active generation found"}
```

**Acceptance criteria**:
- [ ] Cancels streaming generation
- [ ] Returns appropriate status
- [ ] Cleans up resources

---

#### Task D.3: RAG Toggle Integration 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to modify**:
- `app/app/main.py`
- `app/app/schemas.py`

**Implementation**:
```python
class ChatRequest(BaseModel):
    # ... existing ...
    rag_enabled: bool | None = None  # None = use default for provider

# In endpoint
if request.rag_enabled is False:
    # Skip RAG injection
    pass
elif request.rag_enabled is True or (request.provider == "cloud"):
    # Apply RAG
    messages = inject_rag_context(messages, ...)
```

**Acceptance criteria**:
- [ ] RAG can be toggled per request
- [ ] Defaults sensible per provider
- [ ] Toggle state in frontend settings respected

---

#### Task D.4: MCP Tools for Local Model 🔀
**⏳ BLOCKED BY**: Phase 0 complete

**Files to modify**:
- `app/app/services/ollama_client.py`
- `app/app/mcp/manager.py`

**Implementation**:
- Ensure Ollama client formats tool calls correctly
- Handle Qwen 2.5's tool calling format
- Parse tool responses from local model

**Acceptance criteria**:
- [ ] Local model can invoke MCP tools
- [ ] Tool results returned to model
- [ ] Graceful fallback if tool parsing fails

---

#### Task D.5: Frontend API Integration 🔀
**⏳ BLOCKED BY**: Tasks D.1, D.2

**Files to modify**:
- `src/services/api.ts`

**Implementation**:
```typescript
export async function checkOllamaHealth(): Promise<OllamaHealthResponse> {
  const response = await fetch('/api/ollama/health');
  return response.json();
}

export async function getOllamaModels(): Promise<OllamaModel[]> {
  const response = await fetch('/api/ollama/models');
  return response.json();
}

export async function cancelGeneration(requestId: string): Promise<void> {
  await fetch('/api/chat/cancel', {
    method: 'POST',
    body: JSON.stringify({ request_id: requestId }),
  });
}
```

**Acceptance criteria**:
- [ ] Health check called on app startup
- [ ] Model list populates selector
- [ ] Cancel function integrated with stop button

---

## Phase 1 Completion Checkpoint ✅

Before proceeding to Phase 2, verify all streams complete:

**Stream A (Backend Services)**:
- [ ] Cache service working
- [ ] Summarizer service working
- [ ] Both integrated into router

**Stream B (Frontend Core UI)**:
- [ ] Settings store extended
- [ ] Settings panel complete
- [ ] Provider badge visible
- [ ] Model selector working

**Stream C (Frontend Advanced UI)**:
- [ ] Metrics store working
- [ ] Metrics panel displays
- [ ] Stop button cancels
- [ ] Offline banner shows

**Stream D (Backend Integration)**:
- [ ] Health endpoint works
- [ ] Cancel endpoint works
- [ ] RAG toggle works
- [ ] MCP tools work with local

---

## Phase 2: Integration & Polish (🔒 SEQUENTIAL)

> **CRITICAL**: This phase requires all Phase 1 work complete.
> One developer integrates while others write tests.

### Task 2.1: Wire Frontend to Backend
**Developer**: Frontend Lead
**⏳ BLOCKED BY**: All Phase 1 tasks

**Implementation**:
- Connect settings panel to API
- Wire provider badge to actual state
- Connect stop button to cancel endpoint
- Connect metrics panel to streaming data
- Handle Ollama unavailable state in UI

**Acceptance criteria**:
- [ ] Full round-trip works
- [ ] Settings changes take effect immediately
- [ ] Error states handled gracefully

---

### Task 2.2: Error State UI
**Developer**: Frontend Lead
**⏳ BLOCKED BY**: Task 2.1

**Files to create**:
- `src/components/Chat/OllamaError.tsx`

**Implementation**:
```typescript
export function OllamaErrorDialog({ onRetry, onSwitchToCloud }) {
  return (
    <Dialog>
      <h2>⚠️ Local Model Unavailable</h2>
      <p>Ollama is not running or the model is not loaded.</p>
      <div className="actions">
        <Button onClick={onRetry}>Retry</Button>
        <Button onClick={onSwitchToCloud}>Switch to Cloud</Button>
        <Button variant="link" href="/docs/ollama-setup">Help</Button>
      </div>
    </Dialog>
  );
}
```

**Acceptance criteria**:
- [ ] Shows when Ollama unavailable
- [ ] Retry actually retries
- [ ] Switch to cloud works

---

### Task 2.3: History Transfer on Provider Switch
**Developer**: Backend Lead
**⏳ BLOCKED BY**: Task 2.1

**Implementation**:
- When provider changes mid-conversation, keep history
- Tag historical messages with original model
- New messages use new provider

**Acceptance criteria**:
- [ ] Switching provider keeps conversation
- [ ] Old messages show original model
- [ ] New messages use new model

---

### Task 2.4: UI Polish & Responsiveness
**Developer**: Frontend
**⏳ BLOCKED BY**: Task 2.2

**Implementation**:
- Ensure all new components responsive
- Match existing design system
- Add loading states everywhere needed
- Smooth transitions

**Acceptance criteria**:
- [ ] Mobile-friendly
- [ ] No janky transitions
- [ ] Consistent with existing UI

---

## Phase 3: Testing (🔀 PARALLEL with Phase 2)

> Tests can be written in parallel with Phase 2 integration.

### Task 3.1: Backend Unit Tests 🔀
**Developer**: Backend

**Files to create**:
- `tests/test_ollama_client.py`
- `tests/test_provider_router.py`
- `tests/test_cache.py`
- `tests/test_summarizer.py`

**Test coverage**:
```python
# test_ollama_client.py
class TestOllamaClient:
    async def test_chat_returns_response(self, mock_ollama): ...
    async def test_stream_chat_yields_tokens(self, mock_ollama): ...
    async def test_health_check_available(self, mock_ollama): ...
    async def test_health_check_unavailable(self): ...
    async def test_timeout_handling(self, mock_ollama): ...

# test_provider_router.py
class TestProviderRouter:
    async def test_routes_to_ollama_when_local(self): ...
    async def test_routes_to_openai_when_cloud(self): ...
    async def test_unified_response_format(self): ...
    async def test_streaming_both_providers(self): ...

# test_cache.py
class TestResponseCache:
    async def test_cache_hit(self): ...
    async def test_cache_miss(self): ...
    async def test_cache_key_deterministic(self): ...
    async def test_cache_persists(self): ...

# test_summarizer.py
class TestHistorySummarizer:
    async def test_should_summarize_threshold(self): ...
    async def test_summarize_keeps_recent(self): ...
    async def test_summarize_coherent_output(self): ...
```

**Acceptance criteria**:
- [ ] >80% coverage on new code
- [ ] All tests pass with mocked Ollama
- [ ] No flaky tests

---

### Task 3.2: Frontend Unit Tests 🔀
**Developer**: Frontend

**Files to create**:
- `frontend/src/__tests__/LocalModelSettings.test.tsx`
- `frontend/src/__tests__/ProviderBadge.test.tsx`
- `frontend/src/__tests__/MetricsPanel.test.tsx`

**Acceptance criteria**:
- [ ] Component tests pass
- [ ] Store tests pass
- [ ] No flaky tests

---

### Task 3.3: Integration Tests 🔀
**Developer**: QA / Any

**Files to create**:
- `tests/test_local_model_integration.py`

**Test scenarios**:
- [ ] Full chat flow with local model
- [ ] Provider switching mid-conversation
- [ ] RAG toggle behavior
- [ ] Cache hit/miss scenarios
- [ ] Summarization trigger
- [ ] Cancel/stop generation
- [ ] Error recovery

---

## Phase 4: Documentation & Deployment (🔒 SEQUENTIAL)

> Final phase after all features tested.

### Task 4.1: README Documentation
**Developer**: Any
**⏳ BLOCKED BY**: Phase 2, Phase 3

**Files to modify**:
- `README.md`

**Content**:
```markdown
## Local Model Setup

### Prerequisites
- macOS with Apple Silicon (M1/M2/M3/M4)
- 16GB+ unified memory (24GB recommended for 14B models)

### Installation

1. Install Ollama:
   ```bash
   brew install ollama
   ```

2. Start Ollama:
   ```bash
   ollama serve
   ```

3. Pull recommended model:
   ```bash
   ollama pull qwen2.5:14b
   ```

4. Verify installation:
   ```bash
   curl http://localhost:11434/api/tags
   ```

### Usage
- Open Settings → Local Model
- Toggle "Use Local Model"
- Select model from dropdown
- Adjust parameters as needed

### Troubleshooting
...
```

---

### Task 4.2: Server Deployment
**Developer**: DevOps / Backend Lead
**⏳ BLOCKED BY**: Task 4.1

**Steps**:
1. SSH to server
2. Install Ollama
3. Pull model
4. Configure systemd service for Ollama
5. Update docker-compose if needed
6. Test end-to-end

**Acceptance criteria**:
- [ ] Ollama running on server
- [ ] Model loaded and responding
- [ ] App connects to server's Ollama
- [ ] Health check passes

---

### Task 4.3: Final Verification
**Developer**: All
**⏳ BLOCKED BY**: Task 4.2

**Checklist**:
- [ ] Local development works
- [ ] Server deployment works
- [ ] All tests pass
- [ ] No regressions in cloud functionality
- [ ] Documentation accurate

---

## Timeline Overview

```
Week 1:
├── Day 1-2: Phase 0 (Foundation) - Sequential, 1 developer
│
├── Day 3-5: Phase 1 (Features) - Parallel, 4 developers
│   ├── Stream A: Backend Services
│   ├── Stream B: Frontend Core UI
│   ├── Stream C: Frontend Advanced UI
│   └── Stream D: Backend Integration
│
Week 2:
├── Day 6-7: Phase 2 (Integration) - Sequential, 1-2 developers
│   └── Phase 3 (Testing) - Parallel, 2 developers
│
├── Day 8: Phase 4 (Docs & Deploy) - Sequential
│
└── Day 9: Buffer / Bug fixes
```

---

## Dependency Graph

```
Phase 0 (Sequential)
    │
    ├── 0.1 Config
    │     │
    │     └── 0.2 Ollama Client
    │           │
    │           └── 0.3 Provider Router
    │                 │
    │                 └── 0.4 Schemas
    │                       │
    │                       └── 0.5 Endpoints
    │
    ▼
Phase 1 (Parallel) ─────────────────────────────────────────
    │
    ├── Stream A          ├── Stream B          ├── Stream C          ├── Stream D
    │   │                 │   │                 │   │                 │   │
    │   ├── A.1 Cache     │   ├── B.1 Store     │   ├── C.1 Metrics   │   ├── D.1 Health EP
    │   │     │           │   │     │           │   │     │           │   │
    │   │     └── A.3     │   ├── B.2 Settings  │   └── C.2 Panel     │   ├── D.2 Cancel EP
    │   │                 │   │                 │                     │   │
    │   ├── A.2 Summarize │   ├── B.3 Badge     ├── C.3 Stop Btn     │   ├── D.3 RAG Toggle
    │   │     │           │   │                 │                     │   │
    │   │     └── A.4     │   └── B.4 Selector  └── C.4 Offline      │   ├── D.4 MCP Tools
    │   │                 │                                           │   │
    │   │                 │                                           │   └── D.5 Frontend API
    │
    ▼
Phase 2 (Sequential) ───────────────────────────────────────
    │
    ├── 2.1 Wire Frontend ←── All Phase 1
    │     │
    ├── 2.2 Error UI
    │     │
    ├── 2.3 History Transfer
    │     │
    └── 2.4 Polish
    │
    ▼
Phase 3 (Parallel with Phase 2) ────────────────────────────
    │
    ├── 3.1 Backend Tests
    ├── 3.2 Frontend Tests
    └── 3.3 Integration Tests
    │
    ▼
Phase 4 (Sequential) ───────────────────────────────────────
    │
    ├── 4.1 Documentation
    │     │
    ├── 4.2 Server Deploy
    │     │
    └── 4.3 Final Verify
```

---

## Risk Mitigation

### Risk: Response Quality Gap
**Mitigation tasks**:
- Test with real queries during Phase 1
- Prepare fallback messaging in UI
- Easy switch to cloud if local inadequate

### Risk: Breaking Existing Features
**Mitigation tasks**:
- Phase 0 explicitly tests cloud still works
- Integration tests verify no regression
- Feature flag to disable local entirely

### Risk: Integration Complexity
**Mitigation tasks**:
- Clear interfaces between components
- Phase 0 establishes contracts
- Each stream has defined acceptance criteria

---

## Developer Assignment Suggestion

| Developer | Primary Stream | Skills Needed |
|-----------|----------------|---------------|
| Dev 1 (Lead) | Phase 0 + Stream A | Python, async, caching |
| Dev 2 | Stream B | React, TypeScript, state management |
| Dev 3 | Stream C | React, TypeScript, UX |
| Dev 4 | Stream D | Python, FastAPI, API design |

---

*Implementation plan for SPEC_DAY_25_LOCAL_LLM.md*
