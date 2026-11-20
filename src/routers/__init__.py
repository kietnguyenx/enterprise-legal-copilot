from .analytics import router as analytics_router
from .sessions import router as sessions_router
from .audit import router as audit_router
from .feedback import router as feedback_router
from .laws import router as laws_router

__all__ = [
    "analytics_router",
    "sessions_router",
    "audit_router",
    "feedback_router",
    "laws_router",
]
