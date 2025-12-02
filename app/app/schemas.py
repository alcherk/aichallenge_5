from typing import List, Literal, Optional
from pydantic import BaseModel


Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None


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
