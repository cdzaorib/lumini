"""Run with: uvicorn lumini.app:create_app --factory --host 127.0.0.1 --port 8000."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal, cast

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lumini.resources import DependencyStatus, Resources, check_dependency, open_resources
from lumini.settings import Settings


class Liveness(BaseModel):
    status: Literal["alive"] = "alive"


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, DependencyStatus]


def get_resources(request: Request) -> Resources:
    return cast(Resources, request.app.state.resources)


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
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Content-Type"],
        )

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
