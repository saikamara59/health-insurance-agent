"""Request-scoped correlation ID for chaining related agent invocations.

The `case_id` ContextVar travels with the request through every agent
call, so the forensics tool can reconstruct "what did agents A, B, C all
do for case X?" without best-effort timestamp matching.

Two ingress paths:
  * X-Case-Id request header — caller-supplied UUID, validated. Useful when
    a multi-step broker workflow wants to tie together several /compare,
    /verify, /temporal/plan calls under one case.
  * Auto-generated — a fresh uuid4() per request if no header was supplied
    (or if the supplied value was malformed).

Like `current_broker_id`, this module knows nothing about SQLAlchemy or
FastAPI itself; the middleware in `CaseContextMiddleware` is the boundary.
"""
import logging
import uuid
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Default `None` — sync scripts, tests, and pre-middleware contexts have no
# case. Code that needs one (`InvocationLogger`) records `None` when unset
# rather than fabricating a uuid; that keeps the auto-generation responsibility
# in exactly one place (the middleware).
case_id: ContextVar[uuid.UUID | None] = ContextVar("case_id", default=None)


def parse_case_id_header(header_value: str | None) -> uuid.UUID:
    """Return a validated UUID for the X-Case-Id header value.

    Invalid or missing → log WARN + return a fresh uuid4(). Never raises.
    """
    if not header_value:
        return uuid.uuid4()
    try:
        return uuid.UUID(header_value)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid X-Case-Id header (not a UUID); generating fresh case_id. value=%r",
            header_value,
        )
        return uuid.uuid4()
