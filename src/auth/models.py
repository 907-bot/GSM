from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import hashlib
import secrets


class UserRole(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"
    API = "api"


class User(BaseModel):
    id: str = Field(default_factory=lambda: secrets.token_hex(16))
    email: str
    password_hash: str
    name: str = ""
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    api_key: str = Field(default_factory=lambda: f"gsk-{secrets.token_hex(24)}")
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = ""
    role: UserRole = UserRole.RESEARCHER


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class TokenPayload(BaseModel):
    sub: str
    exp: int
    iat: int
    type: str = "access"
    role: str = "viewer"


class TokenRefresh(BaseModel):
    refresh_token: str
