import asyncio
from server import market_mood

async def test():
    result = await market_mood()
    print("Market Mood Output:")
    print(result)

if __name__ == "__main__":
    asyncio.run(test())
