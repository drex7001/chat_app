from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

class ConversationStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), index=True)
    crm_thread_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    customer_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(SAEnum(ConversationStatus), default=ConversationStatus.OPEN, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent_state: Mapped["AgentState"] = relationship("AgentState", back_populates="conversation", uselist=False)

class AgentState(Base):
    __tablename__ = "agent_state"
    
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON, default={})
    version: Mapped[int] = mapped_column(Integer, default=1)
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="agent_state")
