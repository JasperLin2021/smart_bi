from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), default="user")  # user | org_admin | super_admin
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

    organization = relationship("Organization", backref="users")
