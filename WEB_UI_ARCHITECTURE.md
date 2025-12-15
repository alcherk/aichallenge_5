# Web UI Architecture

## Current State Analysis

### Existing Architecture
- **Framework**: Vanilla JavaScript (no framework)
- **File Structure**:
  - Single HTML template (`chat.html`)
  - Monolithic JS file (`chat.js` - ~1000 lines)
  - Single CSS file (`styles.css`)
- **State Management**: Direct localStorage manipulation scattered throughout code
- **Rendering**: Manual DOM manipulation
- **Type Safety**: None
- **Build Process**: None - files served raw

### Current Features
1. Real-time chat with SSE streaming
2. Metrics panel (token usage, costs, response times)
3. Settings panel (model selection, temperature, system prompt)
4. Conversation history persistence (localStorage)
5. Automatic conversation compression
6. Markdown rendering
7. JSON detection and syntax highlighting

### Pain Points
1. **Maintainability**: 1000-line JavaScript file is difficult to maintain and extend
2. **No Separation of Concerns**: UI logic, state management, API calls, and formatting all mixed
3. **No Component Reusability**: Code duplication for similar UI patterns
4. **Testing**: No structure for unit/integration tests
5. **Type Safety**: Runtime errors from undefined/null values
6. **Performance**: No optimization (bundle splitting, lazy loading, memoization)
7. **Scalability**: Adding features requires modifying large functions

---

## Technology Stack

### Frontend Framework: React + TypeScript

**Stack:**
```
Frontend:
- React 18+ (with hooks)
- TypeScript
- Vite (build tool - fast, modern)
- TanStack Query (React Query) - server state management
- Zustand or Jotai - client state management
- Tailwind CSS - utility-first styling
- Radix UI or shadcn/ui - accessible component primitives
- React Markdown - markdown rendering
- EventSource API - SSE streaming
```

**Project Structure:**
```
frontend/
├── src/
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── MessageList.tsx
│   │   ├── metrics/
│   │   │   ├── MetricsPanel.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   └── ContextUsageBar.tsx
│   │   ├── settings/
│   │   │   ├── SettingsPanel.tsx
│   │   │   ├── ModelSelector.tsx
│   │   │   ├── TemperatureSlider.tsx
│   │   │   └── SystemPromptEditor.tsx
│   │   ├── ui/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Slider.tsx
│   │   │   └── Panel.tsx
│   │   └── layout/
│   │       ├── AppLayout.tsx
│   │       ├── Header.tsx
│   │       └── Footer.tsx
│   ├── hooks/
│   │   ├── useChat.ts
│   │   ├── useChatStream.ts
│   │   ├── useMetrics.ts
│   │   ├── useSettings.ts
│   │   └── useLocalStorage.ts
│   ├── services/
│   │   ├── api.ts
│   │   ├── streaming.ts
│   │   └── storage.ts
│   ├── store/
│   │   ├── chatStore.ts
│   │   ├── metricsStore.ts
│   │   └── settingsStore.ts
│   ├── types/
│   │   ├── chat.ts
│   │   ├── api.ts
│   │   └── metrics.ts
│   ├── utils/
│   │   ├── markdown.ts
│   │   ├── json.ts
│   │   ├── pricing.ts
│   │   └── formatting.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── vite-env.d.ts
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## Architecture Design

### Key Architecture Patterns

#### 1. Component Hierarchy
```
App
├── AppLayout
│   ├── Header
│   │   ├── Logo
│   │   ├── NewChatButton
│   │   └── SettingsButton
│   ├── MainContent
│   │   ├── ChatContainer
│   │   │   ├── MessageList
│   │   │   │   ├── SystemMessage
│   │   │   │   ├── UserMessage
│   │   │   │   └── AssistantMessage
│   │   │   │       ├── MessageMeta
│   │   │   │       ├── MarkdownContent
│   │   │   │       ├── JSONContent
│   │   │   │       └── MessageStats
│   │   │   └── ChatInput
│   │   └── MetricsPanel (collapsible)
│   │       ├── CurrentMetrics
│   │       ├── ContextUsage
│   │       └── TotalMetrics
│   └── Footer
└── SettingsModal
    ├── ModelSelector
    ├── TemperatureSlider
    ├── SystemPromptEditor
    └── CompressionSettings
```

#### 2. State Management Strategy

**Client State (Zustand):**
```typescript
// store/settingsStore.ts
interface SettingsState {
  systemPrompt: string;
  temperature: number;
  model: string;
  compressionThreshold: number;
  setSystemPrompt: (prompt: string) => void;
  setTemperature: (temp: number) => void;
  setModel: (model: string) => void;
  setCompressionThreshold: (threshold: number) => void;
}

// store/metricsStore.ts
interface MetricsState {
  totalRequests: number;
  totalCost: number;
  currentMetrics: MetricData | null;
  updateMetrics: (data: MetricData) => void;
  resetMetrics: () => void;
}

// store/chatStore.ts
interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  compressHistory: () => Promise<void>;
}
```

**Server State (TanStack Query):**
```typescript
// hooks/useChat.ts
const useSendMessage = () => {
  return useMutation({
    mutationFn: (message: string) => sendChatMessage(message),
    onSuccess: (data) => {
      // Update metrics, add to conversation
    }
  });
};

// hooks/useChatStream.ts
const useChatStream = () => {
  // Handle SSE streaming with EventSource
};
```

#### 3. Type Definitions

```typescript
// types/chat.ts
export type Role = 'system' | 'user' | 'assistant';

export interface Message {
  role: Role;
  content: string;
  timestamp?: number;
}

export interface ChatRequest {
  messages: Message[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatResponse {
  id: string;
  model: string;
  choices: Array<{
    index: number;
    message: Message;
    finish_reason: string | null;
  }>;
  usage?: TokenUsage;
}

export interface StructuredResponse {
  success: boolean;
  status_code: number;
  message: string;
  data: ChatResponse | null;
  error: {
    type: string;
    detail: string;
  } | null;
  metadata: {
    timestamp: number;
    request_id?: string;
    model: string;
    processing_time_ms: number;
    token_usage?: TokenUsage;
  } | null;
}
```

#### 4. Service Layer

```typescript
// services/api.ts
export const chatAPI = {
  sendMessage: async (request: ChatRequest): Promise<StructuredResponse> => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return response.json();
  },

  streamMessage: (request: ChatRequest) => {
    // Returns EventSource for SSE streaming
  }
};

// services/storage.ts
export const storage = {
  conversation: {
    get: (): Message[] => { /* localStorage logic */ },
    set: (messages: Message[]) => { /* localStorage logic */ },
    clear: () => { /* localStorage logic */ }
  },
  settings: {
    get: () => { /* localStorage logic */ },
    set: (settings: Settings) => { /* localStorage logic */ }
  },
  metrics: {
    get: () => { /* localStorage logic */ },
    set: (metrics: Metrics) => { /* localStorage logic */ }
  }
};
```

#### 5. Custom Hooks

```typescript
// hooks/useChat.ts
export const useChat = () => {
  const messages = useChatStore(state => state.messages);
  const addMessage = useChatStore(state => state.addMessage);
  const { mutate: sendMessage, isPending } = useSendMessage();

  const handleSendMessage = useCallback((content: string) => {
    const userMessage = { role: 'user' as const, content };
    addMessage(userMessage);
    sendMessage(content);
  }, [addMessage, sendMessage]);

  return { messages, sendMessage: handleSendMessage, isPending };
};

// hooks/useChatStream.ts
export const useChatStream = () => {
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const startStream = useCallback(async (request: ChatRequest) => {
    setIsStreaming(true);
    setStreamingContent('');

    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    // Parse SSE and update streamingContent
  }, []);

  return { streamingContent, isStreaming, startStream };
};

// hooks/useLocalStorage.ts
export const useLocalStorage = <T>(key: string, initialValue: T) => {
  const [value, setValue] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setStoredValue = useCallback((newValue: T) => {
    setValue(newValue);
    localStorage.setItem(key, JSON.stringify(newValue));
  }, [key]);

  return [value, setStoredValue] as const;
};
```

---

## Backend Changes Required

### 1. Serve Static Frontend Build

**Update `main.py`:**
```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Serve built frontend (production)
frontend_build_path = Path(__file__).parent / "frontend" / "dist"
if frontend_build_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_build_path), html=True), name="frontend")
else:
    # Development - serve old UI or redirect to dev server
    app.mount("/static", StaticFiles(directory="app/app/static"), name="static")
    templates = Jinja2Templates(directory="app/app/templates")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse("chat.html", {"request": request})
```

### 2. API CORS Configuration (Already Done)

The current CORS configuration allows all origins, which works for development. For production, restrict to specific domains.

### 3. Optional: Add API Versioning

```python
# Group API routes under /api/v1
api_router = APIRouter(prefix="/api/v1")

@api_router.post("/chat", response_model=StructuredResponse)
async def chat(request: ChatRequest):
    # existing logic

app.include_router(api_router)
```

---

## Migration Plan

### Phase 1: Setup Modern Tooling
1. Initialize Vite + React + TypeScript project in `frontend/` directory
2. Configure Tailwind CSS
3. Set up TypeScript types matching backend schemas
4. Create basic component structure
5. Set up state management (Zustand)

### Phase 2: Core Chat Features
1. Implement ChatContainer, MessageList, ChatInput components
2. Migrate message rendering (markdown, JSON formatting)
3. Implement SSE streaming with proper types
4. Add localStorage persistence
5. Connect to existing `/api/chat` and `/api/chat/stream` endpoints

### Phase 3: Settings & Metrics
1. Build SettingsPanel with model selector, temperature, system prompt
2. Implement MetricsPanel with token tracking and cost calculation
3. Add context window visualization
4. Migrate total metrics tracking

### Phase 4: Advanced Features
1. Implement conversation compression UI
2. Add message export functionality
3. Implement dark mode toggle
4. Add keyboard shortcuts (Ctrl+Enter to send, etc.)
5. Optimize performance (memoization, virtualization for long chats)

### Phase 5: Testing & Polish
1. Write unit tests for utilities (pricing, markdown, JSON parsing)
2. Write integration tests for components
3. Add error boundaries
4. Implement loading skeletons
5. Accessibility improvements (ARIA labels, keyboard navigation)
6. Bundle optimization

### Phase 6: Deployment
1. Build production bundle
2. Update Dockerfile to build frontend during image build
3. Configure FastAPI to serve built frontend
4. Test deployed version
5. Performance profiling and optimization

---

## Development Workflow

### Local Development

**Terminal 1 - Backend:**
```bash
cd /Users/lex/Projects/ai/AI_Challenge_5/week1_day1
source .venv/bin/activate
uvicorn app.app.main:app --reload --host 0.0.0.0 --port 8333
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev  # Vite dev server on port 5173
```

Frontend will proxy API requests to `localhost:8333`.

### Vite Configuration

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8333',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8333',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  }
})
```

---

## Updated Dockerfile

```dockerfile
FROM node:18-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./app/app/frontend/dist

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8333

EXPOSE 8333

CMD ["uvicorn", "app.app.main:app", "--host", "0.0.0.0", "--port", "8333"]
```

---

## Architecture Benefits

### Developer Experience
- **TypeScript**: Catch errors at compile time, better IDE autocomplete
- **Component Reusability**: Build once, use everywhere
- **Hot Module Replacement**: Instant feedback during development
- **Better Debugging**: React DevTools, source maps

### Performance
- **Code Splitting**: Load only what's needed
- **Tree Shaking**: Remove unused code
- **Memoization**: Avoid unnecessary re-renders
- **Virtual Scrolling**: Handle thousands of messages efficiently

### Maintainability
- **Modular Structure**: Easy to locate and modify features
- **Separation of Concerns**: UI, logic, state, and API clearly separated
- **Testability**: Each component/hook can be tested in isolation
- **Documentation**: TypeScript types serve as documentation

### Scalability
- **Easy to Add Features**: Plugin architecture for new functionality
- **Multiple Developers**: Clear module boundaries prevent conflicts
- **Code Quality**: Linting, formatting, type checking automated

---

## Testing Strategy

```typescript
// __tests__/utils/pricing.test.ts
import { describe, it, expect } from 'vitest';
import { calculateCost, getModelPricing } from '@/utils/pricing';

describe('pricing utilities', () => {
  it('calculates cost correctly for gpt-4o-mini', () => {
    const cost = calculateCost('gpt-4o-mini', 1000, 500);
    expect(cost).toBeCloseTo(0.00045, 6);
  });
});

// __tests__/components/ChatMessage.test.tsx
import { render, screen } from '@testing-library/react';
import { ChatMessage } from '@/components/chat/ChatMessage';

describe('ChatMessage', () => {
  it('renders user message correctly', () => {
    render(<ChatMessage role="user" content="Hello" />);
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });
});
```

---

## Summary

This React + TypeScript architecture provides:
1. Dramatically improved code maintainability
2. Faster feature development
3. Better type safety and fewer runtime errors
4. Foundation for scaling to multiple developers
5. Improved performance through optimization techniques

The phased migration approach:
- Keeps the current UI working during development
- Tests new features incrementally
- Allows switching to the new UI when ready
- Minimizes deployment risks

**Implementation Approach:**
1. Set up frontend project structure
2. Implement features phase by phase
3. Maintain backward compatibility during migration
4. Switch to new UI after thorough testing
