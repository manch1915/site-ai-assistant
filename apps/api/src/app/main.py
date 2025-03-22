from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from app.api.admin import auth as admin_auth
from app.api.admin import inbox as admin_inbox
from app.api.admin import knowledge as admin_knowledge
from app.api.widget import router as widget_router
from app.container import Container, get_container
from app.infra.db.session import dispose_database

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


def create_app(container: Container | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container or get_container()
        yield
        await app.state.container.redis.aclose()
        await dispose_database()

    app = FastAPI(title="Relay API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def widget_cors(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """The widget runs on customer sites, so CORS mirrors the Origin.

        Whether that origin may actually use a given site key is checked per request.
        """
        if not request.url.path.startswith("/v1/widget"):
            return await call_next(request)
        origin = request.headers.get("origin")
        if request.method == "OPTIONS":
            response: Response = Response(status_code=204)
        else:
            response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Visitor-Token"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers["Vary"] = "Origin"
        return response

    app.include_router(widget_router)
    app.include_router(admin_auth.router)
    app.include_router(admin_knowledge.router)
    app.include_router(admin_inbox.router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
