
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import certifi

async def test_mongo():
    load_dotenv()
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME')
    print(f"Connecting to {mongo_url.split('@')[-1]}...")
    
    try:
        if "mongodb+srv" in mongo_url:
            client = AsyncIOMotorClient(mongo_url, tls=True, tlsCAFile=certifi.where())
        else:
            client = AsyncIOMotorClient(mongo_url)
        
        db = client[db_name]
        # server_info() is a simple command to check connection
        info = await client.server_info()
        print("Successfully connected to MongoDB!")
        print(f"Database: {db_name}")
        
        # Test a query
        count = await db.users.count_documents({})
        print(f"Users count: {count}")
        
    except Exception as e:
        print(f"FAILED to connect to MongoDB: {e}")

if __name__ == "__main__":
    asyncio.run(test_mongo())
