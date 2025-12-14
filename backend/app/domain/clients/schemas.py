from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# --- Config Schemas ---

class PromptConfig(BaseModel):
    system_instruction: str = Field(..., description="Main system prompt for the agent")
    task_specific_prompts: Dict[str, str] = Field(default_factory=dict, description="Specific prompts for different tasks (e.g., 'refund', 'support')")

class PolicyDocument(BaseModel):
    name: str
    content: str

class PolicyConfig(BaseModel):
    documents: List[PolicyDocument] = Field(default_factory=list)
    rules: Dict[str, Any] = Field(default_factory=dict, description="Machine readable rules e.g. {'max_refund': 500}")

class AgentConfig(BaseModel):
    name: str = "Assistant"
    role: str = "orchestrator"
    instructions: str
    model: str = "gpt-4o-mini"
    tools: List[str] = []

class ClientConfig(BaseModel):
    agents: Dict[str, AgentConfig] = {}

# --- Client Schemas ---

class ClientBase(BaseModel):
    name: str
    external_id: str
    config: ClientConfig = ClientConfig()
    policies: PolicyConfig = PolicyConfig(documents=[], rules={})

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[ClientConfig] = None
    policies: Optional[PolicyConfig] = None

class ClientResponse(ClientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

