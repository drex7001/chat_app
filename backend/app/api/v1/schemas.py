from pydantic import BaseModel
from typing import Optional, Dict, Any

class AIMessageRequest(BaseModel):
    message_id: str
    thread_id: str
    client_external_id: str # Keep this for backward compatibility
    app_name: Optional[str] = None # Add this alias/field
    sender_type: str = "customer" # customer, agent
    text: str
    metadata: Optional[Dict[str, Any]] = None

class AIMessageResponse(BaseModel):
    reply_text: str
    conversation_id: int
    metadata: Optional[Dict[str, Any]] = None
