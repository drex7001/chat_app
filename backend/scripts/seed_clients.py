import asyncio
import sys
import os

# Add backend directory to sys.path to allow imports from app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import AsyncSessionLocal, engine
from app.domain.clients.models import Client
from app.domain.agents.definition import NEW_ARCHITECTURE_AGENTS
from sqlalchemy import select, text

# New structure for client data, using NEW_ARCHITECTURE_AGENTS keys
CLIENTS = [
    {"name": "Sania Maskatiya", "external_id": "sania", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Momina Teli", "external_id": "momina", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Leila", "external_id": "leila", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Asim Jofa", "external_id": "asimjofa", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "SAHAR Online", "external_id": "saharonline", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "LALS", "external_id": "lals", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "SUNNIA MANAHIL", "external_id": "manahil", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Nadia Farooqui", "external_id": "nadia", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Nida Azwer Atelier", "external_id": "nidaazwer", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Miaasa", "external_id": "miaasa", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "The Chyll Store", "external_id": "chyll", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Nimra Kashif", "external_id": "nimrakashif", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Spring & Summer", "external_id": "sns", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Zigzag (Pvt.) Ltd", "external_id": "zigzag", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Neeks Closet", "external_id": "neekscloset", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Arienti Pvt Ltd", "external_id": "arienti", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Zainab Chottani", "external_id": "zainabchottani", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Noorma Kaamal", "external_id": "noormakaamal", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "WARDHA SALEEM", "external_id": "wardhasaleem", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Amna Arshad", "external_id": "amnaarshad", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Umsha by Uzma Babar", "external_id": "umsha", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Sumaira Khanani", "external_id": "sumairakhanani", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Sunday Linens", "external_id": "sundaylinen", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Zuri by Zainab Fawad", "external_id": "zuribyzainabfawad", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Little Pineapple", "external_id": "littlepineapple", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Sapphire Retail Limited (SRL)", "external_id": "sapphire", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Tiya", "external_id": "tiya", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Online Bazaar", "external_id": "onlinebazaar", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Shamsha Hashwani", "external_id": "shamshahashwani", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Mina Hasan", "external_id": "mina", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Bonanza Satrangi", "external_id": "bonanza", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Ayesha Ibrahim", "external_id": "ayesha", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Murk", "external_id": "murk", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Sarah Sheeraz", "external_id": "sarah", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Kiki & Boo", "external_id": "kiki", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Nizka Couture", "external_id": "nizka", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Vi’da New York", "external_id": "vida", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
    {"name": "Shamaeel Ansari", "external_id": "shamaeel", "agents": ["triage_agent", "sales_agent", "ops_agent", "support_agent"]},
]

async def seed():
    print("Starting seed process...")
    async with AsyncSessionLocal() as session:
        print("Seeding/Updating clients...")
        for client_data in CLIENTS:
            # Check if exists by ID ONLY to avoid fetching bad JSON
            stmt = select(Client.id).where(Client.external_id == client_data["external_id"])
            result = await session.execute(stmt)
            existing_id = result.scalar_one_or_none() # Returns integer ID or None

            # Prepare agents config using templates
            agent_config = {}
            for agent_key in client_data["agents"]:
                if agent_key in NEW_ARCHITECTURE_AGENTS:
                    # Copy template
                    agent_def = NEW_ARCHITECTURE_AGENTS[agent_key].copy()
                    # Customize instructions with client name
                    # handle both template styles just in case
                    inst = agent_def["instructions"]
                    if "{company_name}" in inst:
                        inst = inst.replace("{company_name}", client_data["name"])
                    agent_def["instructions"] = inst
                    agent_config[agent_key] = agent_def
            
            # Default empty policies if not present
            policies_config = {"documents": [], "rules": {}}

            if existing_id:
                print(f"Updating existing client: {client_data['name']}")
                try:
                    # Use raw text update to ensure JSON is passed as string, bypassing potential TypeDecorator issues
                    import json
                    stmt_text = text("""
                        UPDATE clients 
                        SET name = :name, config = :config, policies = :policies 
                        WHERE id = :id
                    """)
                    await session.execute(stmt_text, {
                        "name": client_data["name"],
                        "name": client_data["name"],
                        "config": json.dumps({"agents": agent_config}),
                        "policies": json.dumps(policies_config),
                        "id": existing_id
                    })
                    print(f"Update executed for {client_data['name']}")
                except Exception as row_error:
                    print(f"Error updating {client_data['name']}: {row_error}")
            else:
                print(f"Creating new client: {client_data['name']}")
                # New client creation also uses model, which might fail if encoding fails. 
                # Let's trust model insert for now, or convert to text verify.
                # But typically insert is fine, checking existence was the blocker.
                new_client = Client(
                    external_id=client_data["external_id"],
                    name=client_data["name"],
                    config={"agents": agent_config, "use_new_architecture": True},
                    policies=policies_config
                )
                session.add(new_client)
        
        await session.commit()

    await engine.dispose()
    print("Seeding completed.")

import traceback

if __name__ == "__main__":
    try:
        # Windows specific event loop policy is already set in common setups but good to ensure
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(seed())
    except Exception as e:
        traceback.print_exc()
