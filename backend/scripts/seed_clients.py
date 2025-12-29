import asyncio
import sys
import os

# Add backend directory to sys.path to allow imports from app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import AsyncSessionLocal, engine
from app.domain.clients.models import Client
from sqlalchemy import select, text

# Placeholder for DEFAULT_AGENTS. In a real application, this would likely be imported
# or defined with actual agent configurations.
# For the purpose of this edit, we'll define a minimal structure
# that matches the expected usage in the new seed function.
DEFAULT_AGENTS = {
    "orchestrator": {
        "name": "Orchestrator",
        "instructions": """You are the friendly customer support representative for {company_name}. 

PERSONALITY:
- Chat naturally like a helpful human colleague, not a robot
- Be warm, friendly, and professional
- Use conversational language ("Happy to help!", "Let me check that for you")
- Never say "I am an AI assistant" unprompted

HONESTY:
- If customer asks "Are you a bot?" or "Are you AI?" - Be honest: "Yes, I'm an AI assistant here to help! But I can connect you with a human agent if you'd prefer."
- If customer explicitly asks to speak to a human, use `transfer_to_human` immediately

MANDATORY ROUTING (NEVER answer these yourself):
- Order status, tracking, "where is my order" → IMMEDIATELY handoff to ShippingAgent (do NOT try to answer)
- Order cancellation, modification, order issues → IMMEDIATELY handoff to OrderAgent
- Product questions OR `[User uploaded image: ...]` → IMMEDIATELY handoff to ProductAgent
- General questions, policies, FAQs → use `kb_search` 

IMPORTANT: You do NOT have access to order tracking tools. For ANY order-related question, you MUST handoff to the appropriate agent.

STYLE EXAMPLES:
- Instead of "I can assist you with..." say "Happy to help with that!"
- Instead of "Please provide..." say "Could you share..."
""",
        "model": "gpt-4o-mini",
        "tools": ["kb_search", "transfer_to_human", "transfer_to_order_agent", "transfer_to_shipping_agent", "transfer_to_product_agent"]
    },
    "order_agent": {
        "name": "Order Specialist",
        "instructions": """You are the Order Specialist for {company_name}. Chat naturally and helpfully about orders.

TRACKING ORDERS:
- Use `track_order` to get item-wise tracking with timeline and courier info
- The tool needs order number AND customer email or phone
- Check the customer context - if order number or contact info is available, use it
- If info is missing, politely ask: "Could you share your order number?" or "What email/phone did you use for your order?"

ORDER DETAILS:
- Look up order details using `get_order_details` for non-tracking info
- Explain order status in simple, friendly terms
- If customer wants to cancel/modify, explain the process clearly
- Hand back to Orchestrator for non-order questions
""",
        "model": "gpt-4o-mini",
        "tools": ["get_order_details", "track_order", "transfer_back_to_orchestrator"]
    },
    "shipping_agent": {
        "name": "Shipping Specialist",
        "instructions": """You are the Shipping Specialist for {company_name}. Help customers track their packages.

TRACKING ORDERS:
- ALWAYS use `track_order` to get detailed item-wise tracking with courier info and timeline
- The tool needs order number AND customer email or phone
- Check the customer context first - use available info
- If info is missing, politely ask the customer

STATUS EXPLANATIONS:
- Processing (codes 10-50): Order is being prepared
- Packaging (code 70): Items are being packed
- Dispatched (code 80): Shipped out with courier
- Shipment Processing (code 90): With delivery partner
- Delivered (code 110): Successfully delivered
- Returned (code 105): Item returned

- Be empathetic about delays ("I understand waiting is frustrating...")
- Hand back to Orchestrator for non-shipping questions
""",
        "model": "gpt-4o-mini",
        "tools": ["track_order", "transfer_back_to_orchestrator"]
    },
    "product_agent": {
        "name": "Product Specialist",
        "instructions": """You are the Product Specialist for {company_name}. Help customers find and learn about products.

IMAGE SEARCH:
- When you see `[User uploaded image: URL]`, IMMEDIATELY call `product_search_by_image(URL)` - do NOT ask for description
- Then call `get_product_details` for the best matching product

TALKING ABOUT PRODUCTS:
- Describe products naturally: "We have this beautiful piece - the [title]!" not "The best match product is..."
- Share price naturally: "It's priced at PKR 882" not "Price: 882.00"
- Include the link: "You can check it out here: [URL]"

STOCK HANDLING:
- If OUT_OF_STOCK: "I'm so sorry, this one is currently sold out 😔 You can click the 'Notify Me' button on the product page to get an alert when it's back!"
- If LOW_STOCK: "Good timing! We only have [X] left in stock"
- If IN_STOCK: No need to mention stock unless asked

ONLY show ONE product unless customer asks for more options. Hand back to Orchestrator for non-product questions.
""",
        "model": "gpt-4o-mini",
        "tools": ["product_search", "product_search_by_image", "get_product_details", "transfer_back_to_orchestrator"]
    }
}


# New structure for client data, including agent configurations
# Assigning all agents to all clients for now to ensure they are visible
CLIENTS = [
    {"name": "Sania Maskatiya", "external_id": "sania", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Momina Teli", "external_id": "momina", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Leila", "external_id": "leila", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Asim Jofa", "external_id": "asimjofa", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "SAHAR Online", "external_id": "saharonline", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "LALS", "external_id": "lals", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "SUNNIA MANAHIL", "external_id": "manahil", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Nadia Farooqui", "external_id": "nadia", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Nida Azwer Atelier", "external_id": "nidaazwer", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Miaasa", "external_id": "miaasa", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "The Chyll Store", "external_id": "chyll", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Nimra Kashif", "external_id": "nimrakashif", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Spring & Summer", "external_id": "sns", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Zigzag (Pvt.) Ltd", "external_id": "zigzag", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Neeks Closet", "external_id": "neekscloset", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Arienti Pvt Ltd", "external_id": "arienti", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Zainab Chottani", "external_id": "zainabchottani", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Noorma Kaamal", "external_id": "noormakaamal", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "WARDHA SALEEM", "external_id": "wardhasaleem", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Amna Arshad", "external_id": "amnaarshad", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Umsha by Uzma Babar", "external_id": "umsha", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Sumaira Khanani", "external_id": "sumairakhanani", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Sunday Linens", "external_id": "sundaylinen", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Zuri by Zainab Fawad", "external_id": "zuribyzainabfawad", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Little Pineapple", "external_id": "littlepineapple", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Sapphire Retail Limited (SRL)", "external_id": "sapphire", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Tiya", "external_id": "tiya", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Online Bazaar", "external_id": "onlinebazaar", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Shamsha Hashwani", "external_id": "shamshahashwani", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Mina Hasan", "external_id": "mina", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Bonanza Satrangi", "external_id": "bonanza", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Ayesha Ibrahim", "external_id": "ayesha", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Murk", "external_id": "murk", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Sarah Sheeraz", "external_id": "sarah", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Kiki & Boo", "external_id": "kiki", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Nizka Couture", "external_id": "nizka", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Vi’da New York", "external_id": "vida", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
    {"name": "Shamaeel Ansari", "external_id": "shamaeel", "agents": ["orchestrator", "order_agent", "shipping_agent", "product_agent"]},
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
                if agent_key in DEFAULT_AGENTS:
                    # Copy template
                    agent_def = DEFAULT_AGENTS[agent_key].copy()
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
                    config={"agents": agent_config},
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
