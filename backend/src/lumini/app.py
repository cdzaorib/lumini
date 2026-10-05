"""Run with: uvicorn lumini.app:create_app --factory --host 127.0.0.1 --port 8000."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal, cast

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lumini.auth import build_identity_verifier
from lumini.booking.google_calendar import build_calendar
from lumini.booking.router import BOOKING_ERRORS, booking_error_handler
from lumini.booking.router import router as booking_router
from lumini.catalog.router import admin_router, public_router
from lumini.resources import DependencyStatus, Resources, check_dependency, open_resources
from lumini.settings import Settings


class Liveness(BaseModel):
    status: Literal["alive"] = "alive"


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, DependencyStatus]


def get_resources(request: Request) -> Resources:
    return cast(Resources, request.app.state.resources)


async def sanitized_validation_error(request: Request, error: Exception) -> JSONResponse:
    """FastAPI's default echoes the submitted input; clinical text and tokens must not return."""
    errors = error.errors() if isinstance(error, RequestValidationError) else []
    detail = [
        {"loc": list(item.get("loc", ())), "type": item.get("type"), "msg": item.get("msg")}
        for item in errors
    ]
    return JSONResponse({"detail": detail}, status_code=422, headers={"Cache-Control": "no-store"})


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_resources(config) as resources:
            app.state.resources = resources
            yield

    app = FastAPI(
        title="Lumini API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if config.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.environment != "production" else None,
    )
    app.state.settings = config
    # Constructing the verifier performs no network work; unconfigured access fails closed.
    app.state.identity_verifier = build_identity_verifier(config)
    # None until the clinic's service account is configured: calendar routes answer 503.
    app.state.calendar = build_calendar(config)
    app.add_exception_handler(RequestValidationError, sanitized_validation_error)
    for error_type in BOOKING_ERRORS:
        app.add_exception_handler(error_type, booking_error_handler)
    if config.cors_origins:
        # Bearer tokens only, never cookies: credentials stay disabled.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "PUT"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )
    app.include_router(admin_router)
    app.include_router(booking_router)
    app.include_router(public_router)

    @app.get("/health/live", response_model=Liveness, tags=["health"])
    async def live() -> Liveness:
        return Liveness()

    @app.get(
        "/health/ready",
        response_model=Readiness,
        responses={503: {"model": Readiness}},
        tags=["health"],
    )
    async def ready(
        response: Response, resources: Annotated[Resources, Depends(get_resources)]
    ) -> Readiness:
        database, redis = await asyncio.gather(
            check_dependency(resources.database, config.dependency_timeout_seconds),
            check_dependency(resources.redis, config.dependency_timeout_seconds),
        )
        checks = {"postgresql": database, "redis": redis}
        is_ready = all(status == "ok" for status in checks.values())
        response.status_code = 200 if is_ready else 503
        response.headers["Cache-Control"] = "no-store"
        return Readiness(status="ready" if is_ready else "not_ready", dependencies=checks)

    return app
