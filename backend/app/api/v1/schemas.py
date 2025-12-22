from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class Attachment(BaseModel):
    url: str
    type: str = "image"  # image, file, audio


class ChatMessage(BaseModel):
    """A single message in conversation history."""
    role: str  # "user" | "assistant"
    content: str


class AIMessageRequest(BaseModel):
    message_id: str
    thread_id: str
    client_external_id: str  # Keep this for backward compatibility
    app_name: Optional[str] = None  # Add this alias/field
    sender_type: str = "customer"  # customer, agent
    text: str
    attachments: Optional[List[Attachment]] = None
    chat_history: Optional[List[ChatMessage]] = None  # Previous messages for multi-turn
    metadata: Optional[Dict[str, Any]] = None

class AIMessageResponse(BaseModel):
    reply_text: str
    conversation_id: int
    metadata: Optional[Dict[str, Any]] = None
