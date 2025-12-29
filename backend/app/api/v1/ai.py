from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.schemas import AIMessageRequest, AIMessageResponse
from app.domain.conversations.service import ConversationService
from app.domain.clients.service import ClientService
from app.domain.crm.client import crm_client
from app.domain.ai_runs.service import AIRunService
from app.domain.ai_runs.models import RunStatus
from app.domain.agents.definition import TOOL_REGISTRY, DEFAULT_AGENTS
from app.domain.agents.context import ClientContext
from app.core.pii_utils import mask_email, mask_phone, redact_pii_for_log
from app.core.config import settings
from agents import Runner
import json

router = APIRouter()

@router.post("/message", response_model=AIMessageResponse)
async def ai_message(
    request: AIMessageRequest, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Main entry point for CRM messages.
    Uses OpenAI Agents SDK with Stateless Injection.
    """
    # Debug output
    client_id_to_use = request.client_external_id or request.app_name
    print(f"DEBUG: Processing message for {client_id_to_use}")

    try:
        # 0. Services
        service = ConversationService(db)
        client_service = ClientService(db)

        # 1. Identify Client
        client = await client_service.get_client_by_external_id(client_id_to_use)
        if not client:
            raise HTTPException(status_code=404, detail=f"Client '{client_id_to_use}' not found")

        # 2. Get/Create Conversation
        conversation = await service.get_or_create_conversation(request.thread_id, client.external_id)

        # 3. Extract customer and order context from request
        customer_email = None
        customer_phone = None
        customer_name = None
        order_number = None
        order_data = None
        
        if request.customer:
            customer_email = request.customer.email
            customer_phone = request.customer.phone
            customer_name = request.customer.name
        
        if request.order:
            order_number = request.order.order_number
            order_data = request.order.model_dump()
        
        # Get tracking key from client config or settings
        tracking_key = None
        if client.config:
            tracking_key = client.config.get("tracking_key") or client.config.get("TRACKING_KEY")
        if not tracking_key:
            tracking_key = settings.TRACKING_KEY

        # 4. Build ClientContext with customer/order data
        client_context = ClientContext(
            app_name=client.external_id,
            policies=client.policies or {},
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_name=customer_name,
            order_number=order_number,
            order_data=order_data,
            tracking_key=tracking_key
        )

        # 4. Reconstruct Agents from Config (Dynamic Loading)
        from agents import Agent
        
        agent_instances = {}
        # Use client config if available, else fallback to DEFAULT_AGENTS
        source_config = client.config.get("agents", {}) if client.config and client.config.get("agents") else DEFAULT_AGENTS
        
        # Pass 1: Create instances
        for key, cfg in source_config.items():
            agent_instances[key] = Agent(
                name=cfg["name"],
                instructions=cfg["instructions"],
                model=cfg["model"],
            )
            
        # Pass 2: Bind tools and handoffs
        for key, cfg in source_config.items():
            agent = agent_instances[key]
            tool_list = []
            handoff_list = []
            
            # Helper to find agent by name or key
            def find_agent(target_name):
                 # Try key match
                 if target_name in agent_instances: return agent_instances[target_name]
                 # Try name match
                 for a in agent_instances.values():
                     if a.name == target_name: return a
                 return None

            for t_name in cfg.get("tools", []):
                if t_name in TOOL_REGISTRY:
                    tool_list.append(TOOL_REGISTRY[t_name])
                elif t_name.startswith("transfer_to_"):
                    # Extract target name (e.g. "order_agent" from "transfer_to_order_agent")
                    target_key = t_name.replace("transfer_to_", "")
                    target_agent = find_agent(target_key)
                    if target_agent:
                        handoff_list.append(target_agent)
                elif t_name.startswith("transfer_back_to_"):
                     target_key = t_name.replace("transfer_back_to_", "")
                     target_agent = find_agent(target_key)
                     if target_agent:
                        handoff_list.append(target_agent)

            # Also support explicit "handoffs" key if present
            for h_key in cfg.get("handoffs", []):
                target_agent = find_agent(h_key)
                if target_agent:
                    handoff_list.append(target_agent)
                    
            agent.tools = tool_list
            agent.handoffs = handoff_list

        # Pick Entry Agent
        if "orchestrator" in agent_instances:
            entry_agent = agent_instances["orchestrator"]
        elif "sales_agent" in agent_instances:
            entry_agent = agent_instances["sales_agent"]
        elif agent_instances:
            entry_agent = list(agent_instances.values())[0]
        else:
             # Should not happen if DEFAULT_AGENTS is populated
             raise HTTPException(status_code=500, detail="No agents configured")

        # 5. Prepare Messages
        messages = []
        if request.chat_history:
            for msg in request.chat_history:
                messages.append({"role": msg.role, "content": msg.content})

        # Handle Attachments (Legacy Strategy: Concatenation)
        combined_text = request.text
        if request.attachments:
            for att in request.attachments:
                if att.type == "image":
                    combined_text += f"\n[User uploaded image: {att.url}]"
                elif att.type == "file":
                    combined_text += f"\n[User uploaded file: {att.url}]"
        
        messages.append({"role": "user", "content": combined_text})
        
        # 5.5 Inject customer context as system message if available
        customer_context_parts = []
        if customer_name or customer_email or customer_phone:
            customer_context_parts.append("[CUSTOMER CONTEXT]")
            if customer_name:
                customer_context_parts.append(f"- Customer Name: {customer_name}")
            if customer_email:
                customer_context_parts.append(f"- Email: {mask_email(customer_email)} (available for tracking)")
            if customer_phone:
                customer_context_parts.append(f"- Phone: {mask_phone(customer_phone)} (available for tracking)")
        
        if order_number:
            customer_context_parts.append(f"- Latest Order: {order_number}")
        
        if customer_context_parts:
            customer_context_parts.append("")
            customer_context_parts.append("You have access to this customer information. Use it when calling tools like track_order.")
            customer_context_parts.append("If required information is missing and user asks about order tracking, politely ask for order number or email/phone.")
            
            # Prepend as system message
            context_message = "\n".join(customer_context_parts)
            messages.insert(0, {"role": "system", "content": context_message})
            print(f"DEBUG: Injected customer context: {context_message}")

        # 6. Run Agent
        print(f"DEBUG: Running agent {entry_agent.name} with {len(messages)} messages")
        start_time = __import__("time").time()
        
        result = await Runner.run(
            entry_agent,
            input=messages,
            max_turns=30,
            context=client_context
        )
        
        latency_ms = int((__import__("time").time() - start_time) * 1000)

        # 7. Log Run & Update State
        run_service = AIRunService(db)
        await run_service.create_run(
            conversation_id=conversation.id,
            client_id=conversation.client_id,
            model=entry_agent.model,
            request_role=request.sender_type,
            status=RunStatus.SUCCESS,
            request_summary=request.text[:500],
            response_summary=result.final_output[:500] if result.final_output else None,
            latency_ms=latency_ms
        )
        
        # Update conversation state
        state = await service.get_agent_state(conversation.id)
        if not state: state = {}
        state["last_message"] = request.text
        state["last_reply"] = result.final_output
        await service.update_agent_state(conversation.id, state)

        return AIMessageResponse(
            reply_text=result.final_output or "No reply generated.",
            conversation_id=conversation.id,
            metadata={
                "model": entry_agent.model,
                "agent": getattr(result, "agent_name", entry_agent.name),
                "input_tokens": getattr(result.usage, "input_tokens", 0) if hasattr(result, "usage") else 0,
                "output_tokens": getattr(result.usage, "output_tokens", 0) if hasattr(result, "usage") else 0
            }
        )

    except Exception as e:
        import traceback
        error_msg = f"ERROR in ai_message: {str(e)}"
        print(error_msg)
        with open("debug_error.log", "a") as f:
            f.write(error_msg + "\n")
            traceback.print_exc(file=f)
        raise HTTPException(status_code=500, detail=str(e))
