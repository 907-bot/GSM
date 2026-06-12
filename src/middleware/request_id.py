"""Request ID middleware — generates and propagates X-Request-Id across the call chain."""

import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import structlog

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that ensures every request has a unique X-Request-Id.

    If the downstream call already provides one (e.g. from nginx), it is
    preserved; otherwise a new UUIDv4 is generated.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-Id")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Make request_id available to downstream handlers
        request.state.request_id = request_id

        # Attach to structlog context
        log = logger.bind(request_id=request_id)
        log.debug("Request started", method=request.method, path=request.url.path)

        response: Response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
