from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings
from app.models.user import User
from app.models.complaint import Complaint


_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    """Initialise Motor client and Beanie ODM.

    Called once at application startup (lifespan event).
    """
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    database = _client[settings.database_name]

    await init_beanie(
        database=database,
        document_models=[User, Complaint],
    )


async def close_db() -> None:
    """Close the Motor connection pool.

    Called once at application shutdown (lifespan event).
    """
    global _client
    if _client is not None:
        _client.close()
        _client = None
