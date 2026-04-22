from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.db import DBSession
from app.config import settings
from app.models.database_models import Store, Staff, StaffRole, Tables
from app.models.authuser import AuthUser
from app.utilities.security import hash_password
from app.utilities.auth import create_access_token
from app.utilities.qr_code import generate_qr_token

router = APIRouter(prefix="/api/debug", tags=["Debug"])

DEBUG_STORE_EMAIL = "debug@localhost"
DEBUG_ADMIN_USERNAME = "admin"
DEBUG_ADMIN_PASSWORD = "admin1234"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 1 day

@router.get("/config")
async def get_debug_config():
    """Returns debug mode status. Frontend uses this to show/hide Debugger button."""
    return {"debug_mode": settings.debug_mode}


@router.post("/init")
async def debug_init(db: DBSession):
    """
    Initialize debug store and admin account, and logs the user in.
    Only works when DEBUG_MODE=true.
    """
    if not settings.debug_mode:
        raise HTTPException(status_code=403, detail="Debug mode is disabled")

    # Get or create debug store
    store = await db.scalar(
        select(Store).where(Store.owner_email == DEBUG_STORE_EMAIL)
    )
    if not store:
        store = Store(owner_email=DEBUG_STORE_EMAIL, name="Debug Store")
        db.add(store)
        await db.flush()

    # Get or create debug admin staff
    admin = await db.scalar(
        select(Staff).where(
            Staff.store_id == store.id,
            Staff.username == DEBUG_ADMIN_USERNAME
        )
    )
    if not admin:
        admin = Staff(
            store_id=store.id,
            username=DEBUG_ADMIN_USERNAME,
            password_hash=hash_password(DEBUG_ADMIN_PASSWORD),
            display_name="Debug Admin",
            role=StaffRole.ADMIN,
            is_active=True,
        )
        db.add(admin)

    # Get or create debug table (number=1, 4 seats)
    debug_table = await db.scalar(
        select(Tables).where(Tables.store_id == store.id, Tables.number == 1)
    )
    if not debug_table:
        debug_table = Tables(
            store_id=store.id,
            number=1,
            number_of_seats=4,
            location="Debug Zone",
            qr_token=generate_qr_token(),
        )
        db.add(debug_table)
        await db.flush()

    # Get or create debug auth_user
    auth_user = await db.scalar(
        select(AuthUser).where(AuthUser.email == DEBUG_STORE_EMAIL)
    )
    if not auth_user:
        auth_user = AuthUser()
        auth_user.email = DEBUG_STORE_EMAIL
        auth_user.name = "Debug Admin"
        auth_user.store_id = store.id
        auth_user.is_registered = True
        db.add(auth_user)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Debug init failed: {e}")


    jwt_token, csrf_token = create_access_token(
        data={
            "sub": str(admin.id),
            "username": admin.username,
            "role": admin.role.name,
            "store_id": admin.store_id,
            "is_registered": True,
        }
    )

    response = JSONResponse(content={
        "message": "Debug store ready and logged in",
        "store_id": store.id,
        "username": admin.username,
        "role": admin.role.name
    })

    # Set the cookies securely
    response.set_cookie(
        key="jwt",
        value=jwt_token,
        httponly=True,
        secure=True,  # Vercel forces HTTPS, so secure=True is required
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    return response


@router.get("/table")
async def get_debug_table(db: DBSession):
    """Returns the debug table's qr_token for the cashier debug QR preview."""
    if not settings.debug_mode:
        raise HTTPException(status_code=403, detail="Debug mode is disabled")

    store = await db.scalar(
        select(Store).where(Store.owner_email == DEBUG_STORE_EMAIL)
    )
    if not store:
        raise HTTPException(status_code=404, detail="Debug store not found. Run /debug/init first.")

    table = await db.scalar(
        select(Tables).where(Tables.store_id == store.id, Tables.number == 1)
    )
    if not table:
        raise HTTPException(status_code=404, detail="Debug table not found. Run /debug/init first.")

    return {"qr_token": table.qr_token, "number": table.number, "seats": table.number_of_seats}