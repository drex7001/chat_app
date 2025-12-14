import sys
import os
import asyncio
sys.path.append(os.getcwd())
import traceback
from sqlalchemy import text
from app.db.session import AsyncSessionLocal, engine

async def sanitize():
    print("Starting database sanitization...")
    async with AsyncSessionLocal() as session:
        print("Resetting all clients to valid empty JSON config...")
        # Force update all rows to have valid JSON
        # We use raw SQL to avoid SQLAlchemy trying to decode the current bad values during a fetch
        import json
        empty_agents = json.dumps({"agents": {}})
        empty_policies = json.dumps({"documents": [], "rules": {}})
        
        stmt = text("""
            UPDATE clients 
            SET config = :config, policies = :policies
        """)
        
        await session.execute(stmt, {"config": empty_agents, "policies": empty_policies})
        await session.commit()
        print("All clients updated to valid default structure.")

    await engine.dispose()

if __name__ == "__main__":
    try:
        # Windows specific event loop policy is already set in common setups but good to ensure
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(sanitize())
    except Exception as e:
        traceback.print_exc()
