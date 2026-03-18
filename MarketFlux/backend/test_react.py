import asyncio
from react_agent import run_react_agent
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

async def test():
    # Simple query about AAPL
    query = "Give me a deep dive on NVDA's balance sheet and recent SEC filings."
    print(f"Testing React Agent with query: {query}")
    
    # We pass None for db to skip mongodb stuff
    stream = run_react_agent(message=query, db=None)
    
    async for event in stream:
        print("EVENT:", event.strip())

if __name__ == "__main__":
    asyncio.run(test())
