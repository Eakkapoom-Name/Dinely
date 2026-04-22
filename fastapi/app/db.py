from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from typing import Annotated
from fastapi import Depends
from app.config import settings
import logging

logger = logging.getLogger(__name__)

try:
    # Simple engine creation for Vercel serverless
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0}  # Required for Supabase PgBouncer (transaction pooler)
    )
    SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Error creating database engine: {e}")
    raise

Base = declarative_base()


async def get_db():
    # "async with" block automatically and safely closes the session when done
    async with SessionLocal() as db:
        yield db

DBSession = Annotated[AsyncSession, Depends(get_db)]