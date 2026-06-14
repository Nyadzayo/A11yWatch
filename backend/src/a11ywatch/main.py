from fastapi import FastAPI

import a11ywatch.models.tables  # noqa: F401  (register ORM models on Base.metadata)
from a11ywatch.api import alert_channels, auth, branding, projects, scans
from a11ywatch.api.errors import register_exception_handlers
from a11ywatch.core.logging import configure_logging
from a11ywatch.web.router import router as web_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="A11yWatch", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(scans.router)
    app.include_router(alert_channels.router)
    app.include_router(branding.router)
    app.include_router(web_router)  # server-rendered dashboard at the app root

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
