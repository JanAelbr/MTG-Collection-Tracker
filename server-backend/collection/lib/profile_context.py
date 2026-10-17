"""Request-scoped active profile (set by the API middleware, read by the connection factory)."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

PROFILE_HEADER = "X-Profile-Id"

_current_profile_id: ContextVar[str | None] = ContextVar("current_profile_id", default=None)


class ProfileNotFoundError(LookupError):
    def __init__(self, profile_id: str | None):
        super().__init__(f"Profile not found: {profile_id!r}")
        self.profile_id = profile_id


def get_current_profile_id() -> str | None:
    return _current_profile_id.get()


def set_current_profile_id(profile_id: str | None) -> Token:
    return _current_profile_id.set(profile_id)


def reset_current_profile_id(token: Token) -> None:
    _current_profile_id.reset(token)


@contextmanager
def profile_scope(profile_id: str | None) -> Iterator[None]:
    token = set_current_profile_id(profile_id)
    try:
        yield
    finally:
        reset_current_profile_id(token)
