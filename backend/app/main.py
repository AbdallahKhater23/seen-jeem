"""تطبيق FastAPI ونقطة التجميع."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.routes import accounts, admin, identity, public
from .config import Settings, load_settings
from .db import init_db
from .schema import SCHEMA_VERSION
from .utils.errors import AppError

logger = logging.getLogger("seenjeem")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(app.state.settings)
    from .services.sync import recover_interrupted_jobs

    interrupted = await recover_interrupted_jobs(app.state.settings)
    logger.info(
        "database ready path=%s schema=%s interrupted_sync_jobs=%s",
        app.state.settings.database_path,
        SCHEMA_VERSION,
        interrupted,
    )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(
        title="Seen Jeem Trivia Engine",
        version="1.0.0",
        description="محرك مباريات وأسئلة محلي مبني على FastAPI وSQLite.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(accounts.router, prefix=settings.api_prefix)
    app.add_middleware(CORSMiddleware, **settings.cors_config)

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "request id=%s method=%s path=%s status=500 duration_ms=%.1f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=exc.as_dict())

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": "المسار غير موجود."
                    if exc.status_code == 404
                    else "العملية غير مسموحة لهذا المسار."
                    if exc.status_code == 405
                    else str(exc.detail),
                    "details": {},
                }
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = []
        for item in exc.errors():
            details.append(
                {
                    "loc": [str(part) for part in item.get("loc", [])],
                    "msg": item.get("msg", "قيمة غير صالحة"),
                    "type": item.get("type", "validation_error"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "بيانات الطلب غير صالحة.",
                    "details": {"errors": details},
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception("unhandled error request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "صار خطأ غير متوقع. جرّب مرة ثانية.",
                    "details": {"request_id": request_id},
                }
            },
        )

    app.include_router(public.router, prefix=settings.api_prefix)
    app.include_router(identity.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)
    return app


app = create_app()
