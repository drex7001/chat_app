import asyncio
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import AsyncSessionLocal
from app.domain.clients.models import Client
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as session:
        stmt = select(Client).where(Client.external_id == "sania")
        result = await session.execute(stmt)
        client = result.scalar_one_or_none()
        
        if client:
            print(f"Client: {client.name}")
            config = client.config
            if isinstance(config, str):
                config = json.loads(config)
            
            p_agent = config.get("agents", {}).get("product_agent", {})
            print(f"Product Agent Tools: {p_agent.get('tools')}")
            print(f"\nProduct Agent Instructions:\n{p_agent.get('instructions')}")
        else:
            print("Client not found")

if __name__ == "__main__":
    if sys.platform == 'win32':
         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check())
