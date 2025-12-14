from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.ai_runs.models import AiRun, RunStatus

class AIRunService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_run(
        self,
        conversation_id: int,
        client_id: int,
        model: str,
        request_role: str,
        status: RunStatus = RunStatus.SUCCESS,
        request_summary: str = None,
        response_summary: str = None,
        latency_ms: int = 0
    ) -> AiRun:
        run = AiRun(
            conversation_id=conversation_id,
            client_id=client_id,
            model=model,
            request_role=request_role,
            status=status,
            request_summary=request_summary,
            response_summary=response_summary,
            latency_ms=latency_ms
        )
        self.db.add(run)
        await self.db.commit()
        return run
