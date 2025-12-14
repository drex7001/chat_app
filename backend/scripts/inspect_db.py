import asyncio
import sys
import os
import json
# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import AsyncSessionLocal, engine
from app.domain.clients.models import Client
from sqlalchemy import select

async def inspect():
    async with AsyncSessionLocal() as session:
        # Check 'sania' or any seeded client
        stmt = select(Client).where(Client.external_id == "sania")
        result = await session.execute(stmt)
        client = result.scalar_one_or_none()
        
        if client:
            print(f"Client: {client.name} ({client.id})")
            print("Config (Agents):")
            # print pretty json
            print(json.dumps(client.config, indent=2))
        else:
            print("Client 'sania' not found.")

    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
