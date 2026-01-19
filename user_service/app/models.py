from sqlalchemy import Column, String, Boolean, Date, Integer, Float, ForeignKey
from sqlalchemy.sql import func
import uuid
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    city = Column(String, nullable=True, index=True)
    country = Column(String, nullable=True)
    last_wash_date = Column(Date, nullable=True)
    preferred_wash_interval = Column(Integer, default=14)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(Date, onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, city={self.city})>"
