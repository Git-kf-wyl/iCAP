"""Routing strategies and registered external model boundaries."""

from .router import (
    FastPathRouter,
    RouteDecision,
    register_classifier_provider,
    register_embedding_provider,
)

__all__ = [
    "FastPathRouter",
    "RouteDecision",
    "register_classifier_provider",
    "register_embedding_provider",
]
