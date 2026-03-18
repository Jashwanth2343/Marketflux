import asyncio
from agent_router import run_agent_pipeline

async def test():
    print("Starting pipeline test...")
    try:
        async for chunk in run_agent_pipeline(message="who is the CEO of XOM?"):
            print("EVENT:", chunk.strip())
    except Exception as e:
        print(f"PIPELINE CRASHED: {e}")

if __name__ == "__main__":
    asyncio.run(test())
