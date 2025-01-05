from sqlalchemy.orm import relationship
from config.db.db import db
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from datetime import datetime


class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    email = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    rol = Column(String, default="User")

    messages = relationship("Message", back_populates="user", order_by="Message.id")
    profile = relationship("Profile", back_populates="user", uselist=False)


class Message(db.Model):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    content = Column(Text, nullable=False)
    author = Column(String, nullable=False)  # 'user' or 'assistant'
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="messages")


class Profile(db.Model):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    favorite_movie_genres = Column(JSON, default=[])
    # Relación con User
    user = relationship("User", back_populates="profile")
