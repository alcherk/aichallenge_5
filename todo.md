# Tasks


## [high] Refactor chatgpt_client.py into smaller modules (id:08483ab2, @alex, due:2026-01-22)

chatgpt_client.py is 1473 lines - a monolith. Split into logical modules:
- rag_handler.py - RAG injection logic
- mcp_handler.py - MCP tool handling
- streaming_handler.py - SSE streaming logic
- task_handler.py - task command processing

## [high] Add JWT authentication for API endpoints (id:35335145, @alex, due:2026-01-25)

Currently API has CORS open to all (allow_origins=["*"]). Implement:
- JWT token generation/validation
- Login/logout endpoints
- Protected route middleware
- Token refresh mechanism

## [high] Implement API endpoint tests (id:9bffac23, @bob, due:2026-01-20)

No tests for /api/chat, /api/chat/stream, /api/mcp/status. Add:
- Unit tests for each endpoint
- Mock OpenAI responses
- Test error handling scenarios
- Test streaming behavior

## [high] Add input validation and sanitization (id:f439926d, @alex, due:2026-01-18)

Beyond Pydantic validation, implement:
- XSS prevention in user messages
- Prompt injection detection
- Max message length enforcement
- Rate limiting per user/IP

## [high] Implement conversation persistence (id:9bbb0623, @bob, due:2026-01-28)

Currently history is browser-only (localStorage). Add:
- SQLite/PostgreSQL storage
- Conversation CRUD API
- User-conversation ownership
- Automatic cleanup of old conversations

## [medium] Add error boundaries to React frontend (id:3aa53619, @frontend, due:2026-01-19)

Unhandled component errors crash entire app. Implement:
- ErrorBoundary wrapper component
- Fallback UI for crashed sections
- Error reporting to backend
- Recovery mechanism

## [medium] Implement retry logic with exponential backoff (id:4f2ec44a, @bob, due:2026-01-21)

Failed API requests don't retry. Add:
- Configurable retry count
- Exponential backoff delays
- Circuit breaker pattern for Chunkenizer
- User feedback during retries

## [medium] Add comprehensive health check endpoint (id:6fb5e00b, @alex, due:2026-01-17)

/health doesn't check dependencies. Enhance to verify:
- OpenAI API connectivity
- Chunkenizer availability
- MCP servers status
- Database connection (when implemented)

## [medium] Implement RAG response caching (id:f7380c71, @bob, due:2026-01-23)

Every RAG query hits Chunkenizer. Add:
- Redis/in-memory cache layer
- TTL-based cache invalidation
- Cache key based on query hash
- Cache hit/miss metrics

## [medium] Add OpenAPI/Swagger documentation (id:773aa9ee, @alex, due:2026-01-19)

API lacks documentation. Generate:
- OpenAPI 3.0 spec from FastAPI
- Swagger UI at /docs
- Request/response examples
- Error code documentation

## [medium] Implement conversation export feature (id:69d7642e, @frontend, due:2026-01-24)

Users cannot export chat history. Add:
- Export as Markdown
- Export as JSON
- Export as PDF (optional)
- Download button in UI

## [medium] Add frontend accessibility improvements (id:090f927d, @frontend, due:2026-01-26)

Limited accessibility in current UI. Implement:
- ARIA labels for all interactive elements
- Keyboard navigation support
- Screen reader announcements
- Focus management for modals

## [low] Add custom model parameters to settings (id:914ba3a9, @bob, due:2026-01-30)

Missing advanced OpenAI parameters. Add UI controls for:
- max_tokens
- top_p (nucleus sampling)
- frequency_penalty
- presence_penalty

## [low] Implement conversation search (id:3bb5010e, @frontend, due:2026-02-01)

Cannot search previous conversations. Add:
- Full-text search across messages
- Filter by date range
- Search by conversation title
- Highlight matches in results

## [low] Add structured logging with request tracing (id:2bf1c44c, @alex, due:2026-01-27)

Logs go to stdout only. Implement:
- JSON structured logging
- Request ID propagation
- Log levels per module
- Optional log aggregation (ELK/Loki)

## [low] Implement Prometheus metrics endpoint (id:d3c64432, @bob, due:2026-02-03)

No observability metrics. Add /metrics with:
- Request latency histograms
- Token usage counters
- Error rate by type
- Active connections gauge

## [low] Add file upload for RAG context injection (id:b426dc2c, @alex, due:2026-02-05)

No document upload support. Implement:
- File upload endpoint
- PDF/TXT/MD parsing
- Temporary RAG context injection
- File size limits and validation

## [low] Create prompt templates library (id:c6b54530, @frontend, due:2026-02-07)

Users write prompts from scratch. Add:
- Pre-made prompt templates
- Category organization
- User template creation
- Template variables support

## [high] Обновить README разделом с новыми командами (id:dc014a81, @alex)
