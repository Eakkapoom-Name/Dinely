# fastapi/app/__init__.py
from fastapi import FastAPI, APIRouter, Request
# from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import Base, engine, SessionLocal
from app.models import database_models as models
from sqlalchemy import select, text
from app.routers import auth
from app.env_detector import should_auto_create_tables
import logging
import os
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from jose import jwt

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("app")

# Detect if running on Vercel (Vercel sets VERCEL=1 automatically)
api_prefix = "/api" #if os.getenv("VERCEL") else ""
logger.info(f"Running with api_prefix: '{api_prefix}' (VERCEL={os.getenv('VERCEL')})")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        if should_auto_create_tables():
            logger.info("Auto-creating database table (docker)")

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(text(
                    "ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS "
                    "is_recommended BOOLEAN NOT NULL DEFAULT FALSE"
                ))
                await conn.execute(text(
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS "
                    "order_number INTEGER"
                ))

            async with SessionLocal() as db:
                exists = await db.scalar(
                    select(models.Categories).where(models.Categories.name == "Recommend")
                )
                if not exists:
                    logger.info("Seeding 'Recommend' category")
                    db.add(models.Categories(name="Recommend", sort_order=0))
                    await db.commit()
        else:
            logger.info("Skipping table creation (Vercel/Local)")
            async with engine.begin() as conn:
                await conn.execute(text(
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS "
                    "order_number INTEGER"
                ))
    except Exception as e:
        logger.error(f"Error during table creation: {e}")

    yield


fastapi_app = FastAPI(
    title="FastAPI Backend",
    debug=settings.debug,
    docs_url=f"{api_prefix}/docs",
    redoc_url=f"{api_prefix}/redoc",
    openapi_url=f"{api_prefix}/openapi.json",
    lifespan=lifespan
)
fastapi_app.logger = logger

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JWTAndCSRFMiddleware(BaseHTTPMiddleware):
    # change when testing post api and data base [25 Feb 2026, 23:32]
    async def dispatch(self, request: StarletteRequest, call_next):
        ## add "docs" and "setcookie_token" to excluded_paths
        excluded_paths = ["/api", "/api/login", "/api/google/auth", "/api/logout", "/api/docs", "/api/setcookie_token", "/api/login/local", "/api/staff/setup", "/api/staff/has_admin", "/api/auth/register"]
        excluded_prefixes = ["/api/qr", "/api/debug"]
        logger.debug(f"Request method: {request.method}, path: {request.url.path}")
        if (request.method not in ["POST", "PUT", "PATCH", "DELETE"]
                or request.url.path in excluded_paths
                or any(request.url.path.startswith(p) for p in excluded_prefixes)):
            logger.debug("Skipping JWT/CSRF validation for this request")
            return await call_next(request)

        # Try staff JWT first, then customer JWT
        token = request.cookies.get("jwt") or request.cookies.get("jwt_customer")
        logger.debug(f"JWT cookie: {token}")
        if not token:
            logger.error("Missing JWT cookie in middleware")
            return JSONResponse(status_code=401, content={"detail": "Missing JWT cookie"})

        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=["HS256"])
            logger.debug(f"JWT payload: {payload}")
        except JWTError as e:
            logger.error(f"JWT decoding failed in middleware: {e}")
            return JSONResponse(
                status_code=401, content={"detail": "Invalid or expired token"})

        client_csrf = request.headers.get("X-CSRF-Token")
        logger.debug(f"Client CSRF token: {client_csrf}")
        if not client_csrf or payload.get("csrf_token") != client_csrf:
            # If first token didn't match CSRF, try the other cookie
            other_token = request.cookies.get("jwt_customer") if request.cookies.get("jwt") else request.cookies.get("jwt")
            if other_token:
                try:
                    other_payload = jwt.decode(other_token, settings.jwt_secret_key, algorithms=["HS256"])
                    if other_payload.get("csrf_token") == client_csrf:
                        # CSRF matches the other token, allow through
                        response = await call_next(request)
                        return response
                except JWTError:
                    pass
            logger.error("CSRF token mismatch in middleware")
            return JSONResponse(status_code=403, content={"detail":"CSRF token mismatch"})

        response = await call_next(request)
        return response


fastapi_app.add_middleware(JWTAndCSRFMiddleware)
fastapi_app.state.settings = settings

# comment these -> already add at the top
# Auto-detect environment and conditionally create tables
# try:
#     if should_auto_create_tables():
#         logger.info("Auto-creating database tables (Docker)")
#         Base.metadata.create_all(bind=engine)
#     else:
#         logger.info("Skipping table creation (Vercel/Local)")
# except Exception as e:
#     logger.error(f"Error during table creation: {e}")
    # Don't fail the app if table creation fails

auth_router = APIRouter()
auth.register_routes(auth_router)
fastapi_app.include_router(auth_router, prefix=api_prefix, tags=["Auth"])
# fastapi_app.include_router(staff.router)
# fastapi_app.include_router(
#     phonebook.router, prefix=f"{api_prefix}/lab10", tags=["Phonebook"])


@fastapi_app.exception_handler(JWTError)
async def jwt_error_handler(request: Request, exc: JWTError):
    fastapi_app.logger.error(f"JWT Error: {exc}")
    return JSONResponse(status_code=401, content={"error": "Invalid token"})


@fastapi_app.exception_handler(ExpiredSignatureError)
async def jwt_expired_error_handler(request: Request, exc: ExpiredSignatureError):
    fastapi_app.logger.error(f"JWT Expired Token Error: {exc}")
    return JSONResponse(status_code=401, content={"error": "Token expired"})

fastapi_app.logger.info(f"Starting FastAPI app with DATABASE_URL: {settings.database_url}")
fastapi_app.logger.debug(f"Allowed origins: {settings.allowed_origins}")
