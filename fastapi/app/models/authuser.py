# fastapi/app/models/authuser.py
import logging
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean

from app.db import Base

logger = logging.getLogger(__name__)


class AuthUser(Base):
    __tablename__ = "auth_users"
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    name = Column(String(1000))
    avatar_url = Column(String(500))
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True, index=True)
    is_registered = Column(Boolean, default=False, server_default="false")
