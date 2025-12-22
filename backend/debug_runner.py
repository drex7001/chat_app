import asyncio
from agents import Runner, Agent

# Dummy Agent
agent = Agent(name="Debug", instructions="You are a helper.", model="gpt-4o-mini")

async def test_string():
    print("--- Testing String Input ---")
    try:
        # Mocking context is hard, so we expect a failure but check traceback? 
        # Actually we need a real run to hit OpenAI.
        # This script might fail if no env var key.
        # But we assume key is present.
        result = await Runner.run(agent, input="Hello", max_turns=1)
        print("Success:", result.final_output)
    except Exception as e:
        print("String Input Failed:", e)

async def test_list():
    print("--- Testing List Input with Context ---")
    try:
        from app.domain.agents.context import ClientContext
        ctx = ClientContext(app_name="debug", policies={})
        msgs = [{"role": "user", "content": "Hello"}]
        result = await Runner.run(agent, input=msgs, max_turns=1, context=ctx)
        print("Success:", result.final_output)
    except Exception as e:
        print("List Input Failed:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test_string())
    asyncio.run(test_list())
