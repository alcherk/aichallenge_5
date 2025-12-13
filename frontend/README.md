# ChatGPT Proxy Frontend

Modern React + TypeScript frontend for the ChatGPT Proxy service.

## Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS v4** - Styling
- **Zustand** - State management
- **React Markdown** - Markdown rendering

## Project Structure

```
src/
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx    # Main chat logic
│   │   ├── ChatMessage.tsx      # Individual message component
│   │   ├── ChatInput.tsx        # Message input form
│   │   └── MessageList.tsx      # Message list with auto-scroll
│   └── layout/
│       ├── AppLayout.tsx        # App shell
│       └── Header.tsx           # Top header
├── store/
│   ├── chatStore.ts             # Chat state (Zustand)
│   ├── settingsStore.ts         # Settings state
│   └── metricsStore.ts          # Metrics state
├── services/
│   ├── api.ts                   # API client
│   ├── storage.ts               # LocalStorage utilities
│   └── streaming.ts             # SSE streaming handler
├── types/
│   ├── chat.ts                  # Chat types
│   ├── settings.ts              # Settings types
│   └── metrics.ts               # Metrics types
├── utils/
│   ├── markdown.ts              # Markdown formatter
│   └── json.ts                  # JSON detection/formatting
├── App.tsx                      # Root component
└── main.tsx                     # Entry point
```

## Development

```bash
# Install dependencies
npm install

# Start dev server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Features Implemented

- ✅ Real-time chat with SSE streaming
- ✅ Message history persistence (localStorage)
- ✅ Markdown rendering for assistant messages
- ✅ JSON detection and syntax highlighting
- ✅ TypeScript type safety throughout
- ✅ Responsive design with Tailwind CSS
- ✅ State management with Zustand
- ✅ Auto-scroll to latest message
- ✅ "New Chat" functionality

## Features Pending

- ⏳ Metrics panel (token usage, costs)
- ⏳ Settings panel (model selection, temperature, system prompt)
- ⏳ Conversation compression
- ⏳ Dark mode
- ⏳ Export conversation

## API Proxy

The dev server proxies API requests to `http://localhost:8333`:
- `/api/*` → Backend API endpoints
- `/health` → Health check endpoint

Make sure the backend is running on port 8333 before starting the frontend dev server.

## Build Output

Production build is output to `dist/` directory. The backend serves this static build in production.
