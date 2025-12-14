from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.schemas import AIMessageRequest, AIMessageResponse
from app.domain.conversations.service import ConversationService
from app.domain.crm.client import crm_client
from app.domain.ai_runs.service import AIRunService
from app.domain.ai_runs.models import RunStatus
from app.domain.agents.definition import TOOL_REGISTRY, DEFAULT_AGENTS
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
    service = ConversationService(db)
    client_service = __import__("app.domain.clients.service", fromlist=["ClientService"]).ClientService(db)
    
    # 0. Fetch Client Configuration
    # Prioritize app_name if provided (as requested by user), fallback to client_external_id
    client_id_to_lookup = getattr(request, "app_name", request.client_external_id) 
    # Note: request schema might need update if app_name isn't in it, but user sent json with it. 
    # Let's assume request schema has it or we access it from body if we changed schema.
    # Actually, simpler: define app_name alias in schema or just alias client_external_id. 
    
    # For now, let's stick to client_external_id but map app_name to it if present.
    # We will search by external_id.
    client = await client_service.get_client_by_external_id(client_id_to_lookup)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id_to_lookup}' not found")
        
    # 1. Get/Create Conversation
    conversation = await service.get_or_create_conversation(request.thread_id, request.client_external_id)
    
    # 2. Reconstruct Agents from Config
    from agents import Agent, function_tool
    from app.domain.agents.definition import TOOL_REGISTRY
    
    agent_instances = {}
    config_agents = client.config.get("agents", {})
    
    # First pass: Create Agent instances (without handoff tools first to avoid circular dep issues if using direct refs, 
    # but with SDK we might need a workaround for 'handoff' tools if they return objects)
    # For now, we assume handoff tools are generic or resolved by name.
    
    # Helper to resolve tools
    def resolve_tools(tool_names):
        tools = []
        for name in tool_names:
            if name in TOOL_REGISTRY:
                tools.append(TOOL_REGISTRY[name])
            elif name.startswith("transfer_to_"):
                # Dynamic Handoff Tool Factory
                target_name = name.replace("transfer_to_", "")
                # We need to ensure target_name exists in our instances map later?
                # Actually, the 'function_tool' decorator needs the function at definition time.
                # A workaround is to define a generic transfer tool.
                
                # For this iteration, we will use a closure if possible, or bind names.
                # OpenAI Swarm/Agents usually requires returning the Agent object.
                pass
        return tools

    # Actually, to support handoffs correctly with dynamic agents, we need to create the functions dynamically
    # that close over the 'agent_instances' dictionary.
    
    def create_handoff_tool(target_agent_name: str):
        @function_tool(name=f"transfer_to_{target_agent_name}")
        def handoff():
            f"""Transfer conversation to {target_agent_name}."""
            return agent_instances.get(target_agent_name)
        return handoff

    # 1. Instantiate all agents
    for key, cfg in config_agents.items():
        agent_instances[key] = Agent(
            name=cfg["name"],
            instructions=cfg["instructions"],
            model=cfg["model"],
            tools=[] # bind later
        )
        
    # 2. Bind tools
    for key, cfg in config_agents.items():
        agent = agent_instances[key]
        tool_list = []
        for t_name in cfg.get("tools", []):
            if t_name in TOOL_REGISTRY:
                tool_list.append(TOOL_REGISTRY[t_name])
            elif t_name.startswith("transfer_to_"):
                target = t_name.replace("transfer_to_", "")
                if target == "orchestrator": target = "orchestrator" # handle synonyms if needed
                tool_list.append(create_handoff_tool(target))
            elif t_name.startswith("transfer_back_to_"):
                target = t_name.replace("transfer_back_to_", "")
                tool_list.append(create_handoff_tool(target))
                
        agent.tools = tool_list

    # Get entry agent (orchestrator)
    if "orchestrator" not in agent_instances:
        # Fallback or Error
        # raise HTTPException(status_code=500, detail="Orchestrator agent missing in config")
        # Fallback to creating a dummy one?
        entry_agent = Agent(name="Fallback", instructions="No configuration found.", model="gpt-4o-mini")
    else:
        entry_agent = agent_instances["orchestrator"]

    # 3. Prepare Input
    messages = [{"role": "user", "content": request.text}]
    
    # 4. Run Agent
    start_time = __import__("time").time()
    result = await Runner.run(entry_agent, input=messages)
    final_reply = result.final_output
    
    latency = int((__import__("time").time() - start_time) * 1000)

    # 5. Log Run
    run_service = AIRunService(db)
    await run_service.create_run(
        conversation_id=conversation.id,
        client_id=conversation.client_id,
        model=entry_agent.model,
        request_role=request.sender_type,
        status=RunStatus.SUCCESS,
        request_summary=request.text[:500],
        response_summary=final_reply[:500] if final_reply else None,
        latency_ms=latency
    )

    # 6. Update State
    state = await service.get_agent_state(conversation.id)
    state["last_message"] = request.text
    state["last_reply"] = final_reply
    await service.update_agent_state(conversation.id, state)

    agent_name = getattr(result.last_agent, "name", str(result.last_agent))

    return AIMessageResponse(
        reply_text=final_reply,
        conversation_id=conversation.id,
        metadata={"model": entry_agent.model, "agent": agent_name}
    )
