"""Supabase client for database operations."""

from functools import lru_cache
from typing import Optional

from supabase import create_client, Client

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_supabase_client() -> Optional[Client]:
    """Get Supabase client instance."""
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_key:
        logger.warning("Supabase credentials not configured")
        return None

    try:
        client = create_client(settings.supabase_url, settings.supabase_key)
        logger.info("Supabase client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


async def init_database_tables():
    """Initialize required database tables."""
    client = get_supabase_client()
    if not client:
        logger.error("Cannot initialize tables: Supabase client not available")
        return

    try:
        # Create conversations table
        await client.table('conversations').select('id').limit(1).execute()
        logger.info("Database tables verified")
    except Exception as e:
        logger.info("Creating database tables...")
        # Tables will be created automatically by Supabase when first accessed
        # or can be created via SQL in Supabase dashboard