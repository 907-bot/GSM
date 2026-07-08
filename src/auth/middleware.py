"""FastAPI dependencies for JWT-based auth and role-based access control."""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, List

from .service import auth_service
from .models import UserRole
from ..config import settings

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """Extract and validate the current user from JWT or API key.

    Checks in order:
    1. Authorization: Bearer <jwt>
    2. X-API-Key header
    """
    user = None

    # Try JWT first
    if credentials:
        user = await auth_service.validate_token(credentials.credentials)

    # Fallback to API key
    if not user:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            api_user = await auth_service.get_user_by_api_key(api_key)
            if api_user:
                user = {
                    "user_id": api_user.id,
                    "email": api_user.email,
                    "role": api_user.role,
                    "name": api_user.name,
                }

    # Fallback to mock admin user in development mode
    if not user and settings.ENVIRONMENT != "production":
        user = {
            "user_id": "dev_admin_id",
            "email": "developer@gsm-os.local",
            "role": UserRole.ADMIN,
            "name": "Developer (Local)",
        }

    if user:
        request.state.user = user
    return user


async def require_auth(
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require a valid authenticated user. Raises 401 if missing."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a valid JWT via Authorization: Bearer <token> or X-API-Key header.",
        )
    return user


def require_role(roles: List[UserRole]):
    """Factory: returns a dependency that requires one of the given roles."""
    async def _role_checker(
        user: Dict[str, Any] = Depends(require_auth),
    ) -> Dict[str, Any]:
        user_role = user.get("role")
        if isinstance(user_role, UserRole):
            user_role = user_role.value
        elif hasattr(user_role, "value"):
            user_role = user_role.value
        allowed = [r.value if isinstance(r, UserRole) else r for r in roles]
        if user_role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user_role}' not permitted. Required one of: {', '.join(allowed)}",
            )
        return user
    return _role_checker


async def optional_user(
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Optional[Dict[str, Any]]:
    """Get user info if authenticated, None otherwise. Never raises."""
    return user
