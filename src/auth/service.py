"""Authentication service: registration, login, token management.

Uses bcrypt for password hashing and PyJWT for secure token handling.
All data persisted via SQLite through the Database layer.
"""

import secrets
import time
from typing import Optional, Dict, Any, List
import structlog
from datetime import datetime, timezone

import bcrypt
import jwt as pyjwt

from ..config import settings
from ..database import db
from .models import UserCreate, UserLogin, TokenResponse, TokenRefresh, UserRole, User

logger = structlog.get_logger()

JWT_ALGORITHM = "HS256"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False


def _create_token(payload: dict, secret: str) -> str:
    return pyjwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _decode_token(token: str, secret: str) -> Optional[dict]:
    try:
        return pyjwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None


class AuthService:
    """Handles user registration, login, and token lifecycle.

    All data persisted in SQLite. Passwords hashed with bcrypt.
    Tokens use PyJWT (RFC 7519 compliant).
    """

    def __init__(self):
        self._user_index: Dict[str, str] = {}  # user_id -> email (fast lookup cache)

    # ── User Management ────────────────────────────────────────────────

    async def register(self, data: UserCreate) -> User:
        if len(data.password) < 8:
            raise ValueError("Password must be at least 8 characters")

        email = data.email.lower().strip()
        existing = await db.get_user_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        user_id = secrets.token_hex(16)
        api_key = f"gsk-{secrets.token_hex(24)}"
        pwd_hash = _hash_password(data.password)
        name = data.name.strip() or email.split("@")[0]

        ok = await db.create_user(
            user_id=user_id,
            email=email,
            password_hash=pwd_hash,
            name=name,
            role=data.role.value if hasattr(data.role, "value") else data.role,
            api_key=api_key,
        )
        if not ok:
            raise ValueError("Failed to create user")

        self._user_index[user_id] = email
        logger.info("User registered", email=email, role=data.role)
        return await self._row_to_user(await db.get_user_by_email(email))

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        row = await db.get_user_by_email(email.lower().strip())
        if not row:
            return None
        if not row.get("is_active"):
            return None
        if not _verify_password(password, row["password_hash"]):
            return None
        await db.update_user_login(row["id"])
        self._user_index[row["id"]] = row["email"]
        return await self._row_to_user(row)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        row = await db.get_user_by_email(email.lower().strip())
        return await self._row_to_user(row) if row else None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        if user_id in self._user_index:
            row = await db.get_user_by_email(self._user_index[user_id])
            if row:
                return await self._row_to_user(row)
        row = await db.get_user_by_id(user_id)
        if row:
            self._user_index[row["id"]] = row["email"]
            return await self._row_to_user(row)
        return None

    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        row = await db.get_user_by_api_key(api_key)
        if row:
            self._user_index[row["id"]] = row["email"]
            return await self._row_to_user(row)
        return None

    async def list_users(self) -> List[User]:
        rows = await db.list_users()
        return [await self._row_to_user(r) for r in rows]

    async def update_role(self, email: str, role: UserRole) -> Optional[User]:
        ok = await db.update_user_role(email, role.value if hasattr(role, "value") else role)
        if not ok:
            return None
        return await self.get_user_by_email(email)

    async def deactivate_user(self, email: str) -> bool:
        return await db.deactivate_user(email)

    async def _row_to_user(self, row: dict) -> Optional[User]:
        if not row:
            return None
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            name=row["name"],
            role=UserRole(row["role"]) if row["role"] in UserRole._value2member_map_ else UserRole.VIEWER,
            is_active=bool(row["is_active"]),
            api_key=row["api_key"],
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now(timezone.utc),
            last_login=datetime.fromisoformat(row["last_login"]) if row.get("last_login") else None,
        )

    # ── Token Management ───────────────────────────────────────────────

    async def create_tokens(self, user: User) -> TokenResponse:
        now = int(time.time())
        access_exp = now + settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        refresh_exp = now + settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400

        access_token = _create_token(
            {
                "sub": user.id,
                "exp": access_exp,
                "iat": now,
                "type": "access",
                "role": user.role.value if hasattr(user.role, "value") else user.role,
            },
            settings.JWT_SECRET_KEY,
        )
        refresh_token = _create_token(
            {
                "sub": user.id,
                "exp": refresh_exp,
                "iat": now,
                "type": "refresh",
            },
            settings.JWT_SECRET_KEY + "_refresh",
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role.value if hasattr(user.role, "value") else user.role,
                "api_key": user.api_key,
            },
        )

    async def refresh_access_token(self, refresh_token: str) -> Optional[TokenResponse]:
        payload = _decode_token(refresh_token, settings.JWT_SECRET_KEY + "_refresh")
        if not payload:
            return None
        user = await self.get_user_by_id(payload.get("sub", ""))
        if not user or not user.is_active:
            return None
        return await self.create_tokens(user)

    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        payload = _decode_token(token, settings.JWT_SECRET_KEY)
        if not payload:
            return None
        if payload.get("type") != "access":
            return None
        user = await self.get_user_by_id(payload.get("sub", ""))
        if not user or not user.is_active:
            return None
        return {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "name": user.name,
        }


auth_service = AuthService()
