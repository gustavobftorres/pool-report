"""
Database models and configuration for user management.
Uses SQLAlchemy ORM with PostgreSQL.
"""
from sqlalchemy import create_engine, Column, BigInteger, String, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import settings

# Database URL from settings
DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """
    Telegram user model.
    Stores user information when they interact with the bot.
    """
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to user's pools
    pools = relationship("UserPool", back_populates="user", cascade="all, delete-orphan")


class UserPool(Base):
    """
    Many-to-many relationship between users and pool addresses.
    Admin assigns pools to users via the Streamlit UI.
    """
    __tablename__ = "user_pools"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    pool_address = Column(String(66), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = relationship("User", back_populates="pools")


def init_db():
    """
    Create all database tables.
    Run this once to initialize the database schema.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency for FastAPI endpoints.
    Provides a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
