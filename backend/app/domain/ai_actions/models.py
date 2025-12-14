from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.db.base import Base

class ActionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"

class CreatedBy(str, enum.Enum):
    AI = "ai"
    HUMAN = "human"

class AiAction(Base):
    __tablename__ = "ai_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), index=True)

    type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[ActionStatus] = mapped_column(SAEnum(ActionStatus), default=ActionStatus.PENDING, index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    
    payload: Mapped[dict] = mapped_column(JSON, default={})
    policy_result: Mapped[dict] = mapped_column(JSON, default={})
    
    created_by: Mapped[CreatedBy] = mapped_column(SAEnum(CreatedBy), default=CreatedBy.AI)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crm_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
