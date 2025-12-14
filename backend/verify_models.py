import sys
import asyncio
from app.db.base import Base
from app.core.config import settings
# Mock settings to avoid error if .env missing? 
# Config uses pydantic settings which will fail if .env missing and no defaults? 
# We set 'ignore' extra, so it should be fine if we set environment vars or if it tolerates missing.
# My config.py has defaults? No, it has explicit fields.
# But I can set environment vars in the process.

from app.domain.clients.models import Client
from app.domain.conversations.models import Conversation, AgentState
from app.domain.ai_actions.models import AiAction
from app.domain.ai_runs.models import AiRun

print("Imports successful")
print(f"Registered tables: {list(Base.metadata.tables.keys())}")
