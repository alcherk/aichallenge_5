from typing import List, Literal, Optional
from pydantic import BaseModel


Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class OllamaOptions(BaseModel):
    """Advanced Ollama generation parameters for optimization."""
    num_ctx: Optional[int] = None  # Context window size (2048-32768)
    num_predict: Optional[int] = None  # Max tokens to generate (128-4096)
    repeat_penalty: Optional[float] = None  # Repetition penalty (1.0-2.0)
    num_gpu: Optional[int] = None  # Number of GPU layers (0-99)
    num_thread: Optional[int] = None  # Number of CPU threads (1-16)


# Prompt mode for conditional system prompts
PromptMode = Literal["auto", "code", "creative", "analysis", "general"]


class ClassificationResult(BaseModel):
    """Result from LLM prompt classifier."""
    category: PromptMode
    confidence: float = 0.0


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = None  # Nucleus sampling parameter
    max_tokens: Optional[int] = None
    # Provider selection: "cloud" (OpenAI) or "local" (Ollama)
    provider: Literal["cloud", "local"] = "cloud"
    # Optional per-request MCP overrides (backward-compatible).
    mcp_enabled: Optional[bool] = None
    mcp_config_path: Optional[str] = None
    workspace_root: Optional[str] = None
    # Assistant mode: strict RAG-only mode
    assistant_mode: Optional[bool] = None
    # RAG toggle: None = use default for provider (cloud=enabled, local=disabled by default)
    rag_enabled: Optional[bool] = None
    # Ollama optimization parameters
    ollama_options: Optional[OllamaOptions] = None
    # Prompt mode for conditional system prompts
    prompt_mode: Optional[PromptMode] = "auto"


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str
    model: str
    choices: List[ChatChoice]
    usage: Optional[ChatUsage] = None
    provider: Optional[Literal["cloud", "local"]] = None


class MessageMetadata(BaseModel):
    """Detailed metadata for message tracking and analytics."""
    model: str
    provider: Literal["cloud", "local"]
    timestamp: float
    tokens_used: Optional[int] = None
    inference_time_ms: Optional[int] = None


class ErrorResponse(BaseModel):
    detail: str


class StructuredResponse(BaseModel):
    """
    Consistent structured response format for tool chaining.
    Always returns the same structure regardless of success or failure.
    """
    success: bool
    status_code: int
    message: str
    data: Optional[ChatResponse] = None
    error: Optional[dict] = None
    metadata: Optional[dict] = None


class CancelRequest(BaseModel):
    """Request body for cancelling an in-progress generation."""
    request_id: str


class CancelResponse(BaseModel):
    """Response for cancel operation."""
    success: bool
    message: str


class TranscribeResponse(BaseModel):
    """Response for speech-to-text transcription."""
    text: str


class ModelInfo(BaseModel):
    """Ollama model information including context limits."""
    name: str
    context_length: int  # Maximum supported context
    default_num_ctx: int  # Default context size
    size_bytes: Optional[int] = None
    modified_at: Optional[str] = None
    parameters: Optional[dict] = None
