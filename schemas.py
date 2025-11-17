"""
Database Schemas for Digital Business Card Platform

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Unique email")
    password_hash: str = Field(..., description="Password hash with salt")
    is_admin: bool = Field(False, description="Admin flag")
    profile_slug: Optional[str] = Field(None, description="Public profile slug, must be unique if set")

class Profile(BaseModel):
    user_id: str = Field(..., description="User ObjectId as string")
    job_title: Optional[str] = None
    company: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    profile_image_path: Optional[str] = None

class SocialLink(BaseModel):
    user_id: str = Field(..., description="User ObjectId as string")
    platform: str = Field(..., description="e.g., linkedin, github, website")
    url: str = Field(..., description="Full URL")
