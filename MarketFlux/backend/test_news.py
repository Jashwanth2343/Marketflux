import asyncio
from market_data import get_ticker_news

async def test():
    print("Testing get_ticker_news for AAPL...")
    articles = await get_ticker_news("AAPL")
    if not articles:
        print("No articles returned.")
        return
        
    for i, art in enumerate(articles[:3]):
        print(f"\n--- Article {i+1} ---")
        print(f"Title: {art.get('title')}")
        print(f"Sentiment: {art.get('sentiment')}")
        print(f"Score: {art.get('sentiment_score')}")

if __name__ == "__main__":
    asyncio.run(test())
