"""Environment detection for Docker vs Vercel deployment"""
import os
import logging

logger = logging.getLogger(__name__)

def detect_environment() -> str:
    """Detect current deployment environment"""
    # Vercel detection
    if os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV"):
        logger.info("Environment detected: Vercel")
        return "vercel"

    # Docker detection
    if os.path.exists("/.dockerenv"):
        logger.info("Environment detected: Docker")
        return "docker"

    # Local development
    logger.info("Environment detected: Local")
    return "local"

def should_auto_create_tables() -> bool:
    """Return True for Docker and Local (Vercel uses manual table creation)"""
    return detect_environment() != "vercel"
