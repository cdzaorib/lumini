"""Shared request dependencies. Tests override them through FastAPI's dependency injection."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lumini.booking.calendar import CalendarAdapter, CalendarNotConfigured

NO_STORE = {"Cache-Control": "no-store"}


def no_store(response: Response) -> None:
    response.headers.update(NO_STORE)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    resources = getattr(request.app.state, "resources", None)
    sessions = cast(async_sessionmaker[AsyncSession] | None, getattr(resources, "sessions", None))
    if sessions is None:
        raise HTTPException(503, "Catalog unavailable", headers=NO_STORE)
    async with sessions() as session:
        yield session


def get_sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    """For work that outlives the request (background replies) or opens several sessions."""
    resources = getattr(request.app.state, "resources", None)
    sessions = cast(async_sessionmaker[AsyncSession] | None, getattr(resources, "sessions", None))
    if sessions is None:
        raise HTTPException(503, "Service unavailable", headers=NO_STORE)
    return sessions


def get_now(request: Request) -> datetime:
    # A single clock per request; tests inject a fixed one through app.state.clock.
    clock = cast(Callable[[], datetime] | None, getattr(request.app.state, "clock", None))
    return clock() if clock is not None else datetime.now(UTC)


def get_calendar(request: Request) -> CalendarAdapter:
    calendar = cast(CalendarAdapter | None, getattr(request.app.state, "calendar", None))
    if calendar is None:
        raise CalendarNotConfigured("Calendar integration is not configured")
    return calendar
