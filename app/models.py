from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Enum
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.orm import relationship
from .database import Base
from enum import Enum as PythonEnum

class UserRole(str, PythonEnum):
	user = "user"
	admin = "admin"

class PrivateMessage(Base):
    __tablename__ = 'private_messages'
    
    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    messages = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    is_read = Column(Boolean, nullable=False, default=True)
    
    sender = relationship("User", foreign_keys=[sender_id])


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    user_name = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    avatar = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    verified = Column(Boolean, nullable=False, server_default='false')
    token_verify = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.user)
    
class User_Status(Base):
    __tablename__ = 'user_status' 
    
    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)
    name_room = Column(String, ForeignKey("rooms.name_room", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),unique=True, nullable=False)
    user_name = Column(String, nullable=False)
    status = Column(Boolean, server_default='True', nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    