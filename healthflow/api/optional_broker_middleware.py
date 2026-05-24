"""ASGI middleware that opportunistically sets current_broker_id from a
bearer token, without enforcing auth.

Why this exists: the older agent routes (/compare, /translate, /verify,
/calculate, /appeal, /estimate) were built before broker accounts and
don't take a `Depends(get_current_broker)`. So even when the frontend
sends a valid token, the request runs with current_broker_id=None and
the InvocationLogger writes broker_id=NULL rows. That breaks forensics
replay: cross-tenant resolution falls back to admin.id and finds zero
rows.

This middleware decodes the bearer (if present and valid) and sets
the ContextVar before the route handler runs. Invalid or missing
tokens are silently ignored — auth requirements on protected routes
are still enforced by their `get_current_broker` dependency.

Teardown ordering matters: when a route ALSO uses get_current_broker,
that dependency calls .set() too. Resetting the dependency's token
restores this middleware's value; resetting this middleware's token
restores None. Both are correct nestings — ContextVar.set/reset pairs
are LIFO.
"""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from healthflow.auth.security import decode_token
from healthflow.auth.tenant_context import current_broker_id


class OptionalBrokerContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token_value: object = None
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            raw = auth.split(" ", 1)[1].strip()
            try:
                payload = decode_token(raw)
                if payload.get("type") == "access":
                    broker_id = uuid.UUID(str(payload["sub"]))
                    token_value = current_broker_id.set(broker_id)
            except Exception:
                # Malformed/expired token — swallow. Protected routes still
                # 401 via their Depends(get_current_broker).
                pass
        try:
            return await call_next(request)
        finally:
            if token_value is not None:
                current_broker_id.reset(token_value)
