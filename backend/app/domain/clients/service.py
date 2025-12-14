from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.domain.clients.models import Client
from app.domain.clients.schemas import ClientCreate, ClientUpdate

class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_client(self, client_in: ClientCreate) -> Client:
        client_data = client_in.model_dump()
        db_client = Client(**client_data)
        self.db.add(db_client)
        await self.db.commit()
        await self.db.refresh(db_client)
        return db_client

    async def get_client(self, client_id: int) -> Optional[Client]:
        return await self.db.get(Client, client_id)

    async def get_client_by_external_id(self, external_id: str) -> Optional[Client]:
        stmt = select(Client).where(Client.external_id == external_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_clients(self, skip: int = 0, limit: int = 100) -> List[Client]:
        stmt = select(Client).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_client(self, client_id: int, client_in: ClientUpdate) -> Optional[Client]:
        db_client = await self.get_client(client_id)
        if not db_client:
            return None
        
        update_data = client_in.model_dump(exclude_unset=True)
        print(f"Updating client {client_id} with data keys: {update_data.keys()}")
        if "config" in update_data:
            print(f"Config update: {update_data['config']}")

        for field, value in update_data.items():
            setattr(db_client, field, value)
            
        self.db.add(db_client)
        await self.db.commit()
        await self.db.refresh(db_client)
        return db_client

