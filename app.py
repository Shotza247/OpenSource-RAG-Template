"""Vercel entry point; hosted services are configured with environment variables."""

from profile_agent.api import app

__all__ = ["app"]
