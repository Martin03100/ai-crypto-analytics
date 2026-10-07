"""Admin role: listed in ADMIN_USERNAMES (environment), so it cannot be granted from the web."""

from __future__ import annotations

from app import config
from app.models import User


def is_admin(user: User) -> bool:
    return bool(user and user.username and user.username.lower() in config.ADMIN_USERNAMES and not user.disabled)
