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
        await db.daily_briefs.create_index([("date", -1), ("user_id", 1)], background=True)
        await db.signal_events.create_index("created_at", background=True)
        await db.saved_theses.create_index([("owner_user_id", 1), ("ticker", 1), ("updated_at", -1)], background=True)
        await db.research_runs.create_index([("owner_user_id", 1), ("created_at", -1)], background=True)
        await db.strategy_runs.create_index([("owner_user_id", 1), ("created_at", -1)], background=True)

        # Pilot subsystem indexes
        await db.pilot_personalities.create_index("id", unique=True, background=True)
        await db.pilot_personalities.create_index("user_id", background=True)
        await db.pilot_trade_proposals.create_index("id", unique=True, background=True)
        await db.pilot_trade_proposals.create_index(
            [("user_id", 1), ("status", 1), ("created_at", -1)], background=True
        )
        await db.pilot_audit_events.create_index(
            [("proposal_id", 1), ("timestamp", 1)], background=True
        )
        await db.pilot_activity_events.create_index(
            [("personality_id", 1), ("timestamp", -1)], background=True
        )
        # Do not create a TTL index on `timestamp` unless writers persist it as a BSON Date.
        # MongoDB TTL indexes do not expire string values, so enabling TTL here would provide
        # a false sense of retention if activity events are stored with ISO-formatted strings.
        logger.warning(
            "Skipping TTL index on pilot_activity_events.timestamp until the field is stored as a BSON Date."
        )
        await db.pilot_user_consent.create_index("user_id", unique=True, background=True)

        # Reflection: journal + thesis drift
        await db.pilot_journal.create_index("id", unique=True, background=True)
        await db.pilot_journal.create_index(
            [("personality_id", 1), ("date", -1)], background=True
        )
        await db.pilot_drift_flags.create_index("id", unique=True, background=True)
        await db.pilot_drift_flags.create_index(
            [("personality_id", 1), ("ticker", 1)], background=True
        )
        await db.pilot_drift_flags.create_index("severity", background=True)
        # Leaderboard / public profile lookups
        await db.pilot_personalities.create_index(
            "public_slug", unique=True, sparse=True, background=True
        )
        await db.pilot_personalities.create_index("public_visibility", background=True)

        # Conviction ledger
        await db.ledger_theses.create_index("id", unique=True, background=True)
        await db.ledger_theses.create_index(
            [("user_id", 1), ("status", 1), ("created_at", -1)], background=True
        )
        await db.ledger_theses.create_index(
            [("user_id", 1), ("agent_id", 1), ("ticker", 1), ("status", 1)], background=True
        )
        await db.ledger_audit.create_index([("thesis_id", 1), ("at", 1)], background=True)
        await db.ledger_daily_closes.create_index(
            [("symbol", 1), ("date", 1)], unique=True, background=True
        )

        logger.info("All MongoDB indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Error initializing indexes: {e}")
