import logging

logger = logging.getLogger(__name__)

async def initialize_indexes(db):
    try:
        await db.news_articles.create_index([("ticker", 1), ("published_date", -1)], background=True)
        await db.news_articles.create_index("url", unique=True, background=True)
        await db.news_articles.create_index("published_date", expireAfterSeconds=604800, background=True)
        await db.news_articles.create_index("is_duplicate", background=True)

        await db.chat_messages.create_index([("user_id", 1), ("created_at", -1)], background=True)
        await db.portfolios.create_index("user_id", background=True)
        await db.watchlists.create_index("user_id", background=True)

        await db.ai_usage.create_index([("user_id", 1), ("date", 1)], background=True)
        await db.ai_usage.create_index("date", expireAfterSeconds=86400, background=True)

        await db.users.create_index("email", unique=True, background=True)
        await db.streams.create_index("user_id", background=True)

        logger.info("All MongoDB indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Error initializing indexes: {e}")
