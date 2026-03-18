import asyncio
import os
from dotenv import load_dotenv

# Load ENV
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from react_agent import run_react_agent

async def test_agent_query(query: str):
    print(f"\n============================================\nQUERY: {query}\n--------------------------------------------")
    full_response = ""
    async for event in run_react_agent(query):
        if event.startswith("data: "):
            try:
                import json
                data = json.loads(event[6:])
                if data["type"] == "thinking":
                    print(f"[{data['step']}] {data['message']}")
                elif data["type"] == "token":
                    full_response += data["content"]
            except Exception:
                pass
                
    print(f"\nFINAL RESPONSE:\n{full_response}\n============================================")

async def main():
    queries = [
        "what's the next earnings date for tesla, what are the consensus expectations",
    ]
    for q in queries:
        await test_agent_query(q)

if __name__ == "__main__":
    asyncio.run(main())
