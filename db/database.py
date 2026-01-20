"""
Database models and configuration.

New schema (client-driven Telegram reports):
- allowed_users: Telegram users who are allowed to interact with the bot
- clients: portfolio/client keys (e.g. "aave")
- client_pools: mapping of client_key -> pool_address
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from config import settings

# Database URL from settings
DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AllowedUser(Base):
    """
    Telegram user model (whitelist).
    Only users present in this table are allowed to request client reports via the bot.
    """

    __tablename__ = "allowed_users"

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)


class Client(Base):
    """
    Client / portfolio grouping (e.g. "aave").
    """

    __tablename__ = "clients"

    client_key = Column(String(64), primary_key=True)  # normalized key, e.g. "aave"
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    pools = relationship("ClientPool", back_populates="client", cascade="all, delete-orphan")


class ClientPool(Base):
    """
    Mapping of client -> pool address.
    """

    __tablename__ = "client_pools"
    __table_args__ = (UniqueConstraint("client_key", "pool_address", name="uq_client_pool"),)

    id = Column(Integer, primary_key=True)
    client_key = Column(String(64), ForeignKey("clients.client_key", ondelete="CASCADE"), nullable=False)
    pool_address = Column(String(66), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="pools")


def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: provide a DB session and close it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
