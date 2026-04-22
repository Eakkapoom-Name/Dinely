#!/usr/bin/env python3
# fastapi/app/routers/auth.py

import logging
import secrets
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from app.schemas.auth import UserResponse, Message, StandardLogin, CustomerQRLogin

from app.models.authuser import AuthUser
from app.models.database_models import Store, Staff, StaffRole, Tables, TableStatus, Customers
from app.db import DBSession
from app.utilities.timezone import BANGKOK_TZ
from app.config import settings
from app.utilities.auth import create_access_token, get_jwt_payload
from app.utilities.security import hash_password, verify_password
from jose import jwt, JWTError
from datetime import datetime, timedelta
from httpx import AsyncClient
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set this logger to DEBUG

router = APIRouter()

# JWT Configuration
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 1 day (1440 minutes)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = settings.google_client_id or "your-google-client-id"
GOOGLE_CLIENT_SECRET = settings.google_client_secret or "your-google-client-secret"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

# Line OAuth Configuration
LINE_APP_ID = settings.line_app_id or "your-line-app-id"
LINE_APP_SECRET = settings.line_app_secret or "your-line-app-secret"
LINE_AUTH_URL = "https://access.line.me/oauth2/v2.1/authorize"
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_USERINFO_URL = "https://api.line.me/v2/profile"


async def get_current_user(request: Request, db: DBSession):
    logger.debug("Checking JWT cookie in get_current_user")
    token = request.cookies.get("jwt")
    logger.debug(f"JWT cookie: {token}")
    if not token:
        logger.error("Missing JWT cookie in get_current_user")
        raise HTTPException(status_code=401, detail="Missing JWT cookie")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"JWT payload: {payload}")
        user_id: str = payload.get("sub")
        logger.debug(f"Extracted user_id from sub: {user_id}")
        if user_id is None:
            logger.error("Invalid token: subject missing")
            raise HTTPException(
                status_code=401, detail="Invalid token: subject missing")
        user = await db.scalar(select(AuthUser).where(AuthUser.id == int(user_id)))
        if user is None:
            logger.error(f"User not found for id: {user_id}")
            raise HTTPException(status_code=401, detail="User not found")
        logger.debug(f"User found: {user.email}")
        return user
    except JWTError as e:
        logger.error(f"JWT decoding failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/", response_model=Message)
async def hello():
    """
    **Root Auth Endpoint**

    Returns a simple greeting message to verify the auth router is active.
    """
    logger.info("Auth hello endpoint accessed")
    return {"message": "From auth.py: Hello World!"}


# For testing
@router.get("/setcookie_token")
async def setcookie_token():
    
    csrf_token = secrets.token_hex(16)

    data = {
        "sub": "999",
        "username": "swagger_tester",
        "role": "admin", 
        "csrf_token": csrf_token,
        "exp": datetime.utcnow() + timedelta(minutes=1440),
        "iat": datetime.utcnow()
    }

    jwt_token = jwt.encode(data, settings.jwt_secret_key, algorithm="HS256")

    response = JSONResponse(content={
        "message": "Test session created successfully!",
        "csrf_token": csrf_token,
        "instructions": "Copy the 'csrf_token' string above and paste it into the 'X-CSRF-Token' field for your POST routes."
    })

    response.set_cookie(
        key="jwt",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    return response


# For testing customer role
@router.get("/setcookie_customer_token")
async def setcookie_customer_token(
    db: DBSession,
    table_id: int = 1,
    customer_name: str = "tester"
):
    table = await db.scalar(select(Tables).where(Tables.id == table_id))
    if not table:
        raise HTTPException(status_code=404, detail=f"No table with id={table_id}")

    now = datetime.now(BANGKOK_TZ)
    session_token = table.session_token or secrets.token_urlsafe(32)

    if table.status != TableStatus.OCCUPIED:
        table.status = TableStatus.OCCUPIED
        table.session_token = session_token
        table.session_started_at = now
        table.updated_at = now

    new_customer = Customers(
        table_id=table.id,
        session_token=session_token,
        name=customer_name,
        token=secrets.token_urlsafe(32),
        is_active=True,
        updated_at=now,
    )
    db.add(new_customer)
    try:
        await db.commit()
        await db.refresh(new_customer)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not create test customer: {e}")

    jwt_token, csrf_token = create_access_token(
        data={
            "sub": str(new_customer.id),
            "role": "customer",
            "table_id": table.id,
            "customer_name": customer_name,
        }
    )

    response = JSONResponse(content={
        "message": "Test customer session created successfully!",
        "customer_id": new_customer.id,
        "table_id": table.id,
        "table_number": table.number,
        "csrf_token": csrf_token,
        "instructions": "Copy the 'csrf_token' string above and paste it into the 'X-CSRF-Token' field for your POST/PATCH/DELETE routes."
    })

    response.set_cookie(
        key="jwt",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    return response


@router.get("/login", response_description="Redirects to Google OAuth")
async def login(request: Request):
    """
    **Initiate Google OAuth Login**

    Constructs the Google OAuth URL with identifying scopes (openid, email, profile)
    and redirects the user to Google's consent page.
    """
    # Use explicitly configured redirect URI (required because Vite proxy's
    # changeOrigin rewrites the Host header, and the Google callback has no
    # usable Referer/Origin from our app).
    redirect_uri = settings.google_oauth_redirect_uri
    if not redirect_uri:
        # Fallback: try to derive from Referer header
        referer = request.headers.get("referer", "")
        if referer:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port and parsed.port not in (80, 443):
                origin += f":{parsed.port}"
            redirect_uri = f"{origin}/api/google/auth"
        else:
            redirect_uri = f"{request.url.scheme}://{request.url.hostname}"
            if request.url.port and request.url.port not in (80, 443):
                redirect_uri += f":{request.url.port}"
            redirect_uri += "/api/google/auth"
    logger.info(f"Google OAuth redirect_uri: {redirect_uri}")
    auth_url = (
        f"{GOOGLE_AUTH_URL}?response_type=code&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}&scope=openid%20email%20profile"
    )
    logger.info("Redirecting to Google OAuth")
    return RedirectResponse(url=auth_url)


@router.get("/google/auth", name="google_auth", response_description="Redirects to Frontend with JWT")
async def google_auth(request: Request, db: DBSession):
    """
    **Google OAuth Callback**

    Handles the callback from Google:
    1. Exchanges the authorization code for an access token.
    2. Fetches user profile information from Google.
    3. New user: creates a Store + AuthUser, redirects to registration.
    4. Existing unregistered user: redirects to registration.
    5. Existing registered user: redirects to dashboard.
    """
    try:
        code = request.query_params.get("code")
        if not code:
            raise ValueError("No authorization code provided")

        # Use the same redirect_uri that was sent to Google (must match exactly)
        callback_redirect_uri = settings.google_oauth_redirect_uri
        if not callback_redirect_uri:
            callback_redirect_uri = f"{request.url.scheme}://{request.url.hostname}"
            if request.url.port and request.url.port not in (80, 443):
                callback_redirect_uri += f":{request.url.port}"
            callback_redirect_uri += "/api/google/auth"

        logger.info(f"Google OAuth callback redirect_uri: {callback_redirect_uri}")

        async with AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": callback_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_response.json()
            if "error" in token_data:
                logger.error(f"Google token exchange failed: {token_data}")
                raise ValueError(f"Google OAuth error: {token_data['error']} - {token_data.get('error_description', '')}")
            access_token = token_data.get("access_token")

            user_info_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info = user_info_response.json()
            logger.debug(f"Google profile: {user_info}")

        email = user_info["email"]
        user = await db.scalar(select(AuthUser).where(AuthUser.email == email))

        if not user:
            # --- New merchant: create Store + AuthUser ---
            logger.debug("New user, creating store and auth_user")
            store = Store(owner_email=email, name=user_info.get("name", "My Store"))
            db.add(store)
            await db.flush()  # get store.id

            user = AuthUser()
            user.email = email
            user.name = user_info["name"]
            user.avatar_url = user_info.get("picture")
            user.store_id = store.id
            user.is_registered = False
            db.add(user)
            await db.commit()
            await db.refresh(user)
            await db.refresh(store)
        else:
            # Update profile info from Google
            user.name = user_info["name"]
            user.avatar_url = user_info.get("picture")
            await db.commit()

        # Build JWT payload based on registration status
        token_data = {
            "sub": str(user.id),
            "auth_user_id": user.id,
            "store_id": user.store_id,
            "is_registered": user.is_registered,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
        }

        if user.is_registered:
            # Find their staff record to include role
            staff = await db.scalar(
                select(Staff).where(
                    Staff.store_id == user.store_id,
                    Staff.role == StaffRole.ADMIN
                )
            )
            if staff:
                token_data["sub"] = str(staff.id)
                token_data["username"] = staff.username
                token_data["role"] = "admin"

        jwt_token, csrf_token = create_access_token(data=token_data)

        frontend_url = settings.frontend_login_success_uri
        logger.info(f"Redirecting to frontend for {email} (registered={user.is_registered})")
        response = RedirectResponse(url=f"{frontend_url}?token={jwt_token}")
        response.set_cookie(
            key="jwt",
            value=jwt_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return response

    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing Google auth callback: {e}")
        return RedirectResponse(url=settings.frontend_login_failure_uri)


@router.get("/login/line", response_description="Redirects to Line OAuth")
async def login_line(request: Request):
    """
    **Initiate Line OAuth Login**

    Constructs the Line OAuth URL and redirects the user to Line's consent page.
    """
    redirect_uri = settings.line_oauth_redirect_uri
    if not redirect_uri:
        referer = request.headers.get("referer", "")
        if referer:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port and parsed.port not in (80, 443):
                origin += f":{parsed.port}"
            redirect_uri = f"{origin}/api/line/auth"
        else:
            redirect_uri = f"{request.url.scheme}://{request.url.hostname}"
            if request.url.port and request.url.port not in (80, 443):
                redirect_uri += f":{request.url.port}"
            redirect_uri += "/api/line/auth"
    state = secrets.token_urlsafe(16)
    logger.info(f"Line OAuth redirect_uri: {redirect_uri}")
    auth_url = (
        f"{LINE_AUTH_URL}?response_type=code&client_id={LINE_APP_ID}"
        f"&redirect_uri={redirect_uri}&scope=profile%20openid%20email"
        f"&state={state}"
    )
    logger.info("Redirecting to Line OAuth")
    return RedirectResponse(url=auth_url)


@router.get("/line/auth", name="line_auth", response_description="Redirects to Frontend with JWT")
async def line_auth(request: Request, db: DBSession):
    """
    **Line OAuth Callback**

    Handles the callback from Line:
    1. Exchanges the authorization code for an access token.
    2. Fetches user profile information from Line.
    3. New user: creates a Store + AuthUser, redirects to registration.
    4. Existing unregistered user: redirects to registration.
    5. Existing registered user: redirects to dashboard.
    """
    try:
        code = request.query_params.get("code")
        if not code:
            error = request.query_params.get("error")
            error_description = request.query_params.get("error_description", "")
            logger.error(f"Line auth denied: {error} - {error_description}")
            return RedirectResponse(url=settings.frontend_login_failure_uri)

        callback_redirect_uri = settings.line_oauth_redirect_uri
        if not callback_redirect_uri:
            callback_redirect_uri = f"{request.url.scheme}://{request.url.hostname}"
            if request.url.port and request.url.port not in (80, 443):
                callback_redirect_uri += f":{request.url.port}"
            callback_redirect_uri += "/api/line/auth"

        logger.info(f"Line OAuth callback redirect_uri: {callback_redirect_uri}")

        async with AsyncClient() as client:
            # Exchange code for access token (LINE requires POST with form data)
            token_response = await client.post(
                LINE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": callback_redirect_uri,
                    "client_id": LINE_APP_ID,
                    "client_secret": LINE_APP_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_data = token_response.json()
            if "error" in token_data:
                logger.error(f"Line token exchange failed: {token_data}")
                raise ValueError(f"Line OAuth error: {token_data.get('error')} - {token_data.get('error_description', '')}")
            access_token = token_data.get("access_token")
            id_token_raw = token_data.get("id_token")

            # Decode id_token to get email (LINE profile API doesn't return email)
            # LINE signs id_tokens with the Channel Secret using HS256
            email = None
            if id_token_raw:
                id_payload = jwt.decode(
                    id_token_raw,
                    LINE_APP_SECRET,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
                email = id_payload.get("email")
                logger.debug(f"Line id_token payload: {id_payload}")

            # Fetch user profile for displayName and pictureUrl
            user_info_response = await client.get(
                LINE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info = user_info_response.json()
            logger.debug(f"Line profile: {user_info}")

        if not email:
            logger.error("Line account has no email (user may not have granted email permission)")
            return RedirectResponse(url=settings.frontend_login_failure_uri)

        name = user_info.get("displayName", "")
        picture_url = user_info.get("pictureUrl")

        user = await db.scalar(select(AuthUser).where(AuthUser.email == email))

        if not user:
            # New merchant: create Store + AuthUser
            logger.debug("New Line user, creating store and auth_user")
            store = Store(owner_email=email, name=name or "My Store")
            db.add(store)
            await db.flush()

            user = AuthUser()
            user.email = email
            user.name = name
            user.avatar_url = picture_url
            user.store_id = store.id
            user.is_registered = False
            db.add(user)
            await db.commit()
            await db.refresh(user)
            await db.refresh(store)
        else:
            # Update profile info from Line
            user.name = name
            user.avatar_url = picture_url
            await db.commit()

        # Build JWT payload (same structure as Google)
        token_data = {
            "sub": str(user.id),
            "auth_user_id": user.id,
            "store_id": user.store_id,
            "is_registered": user.is_registered,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
        }

        if user.is_registered:
            staff = await db.scalar(
                select(Staff).where(
                    Staff.store_id == user.store_id,
                    Staff.role == StaffRole.ADMIN
                )
            )
            if staff:
                token_data["sub"] = str(staff.id)
                token_data["username"] = staff.username
                token_data["role"] = "admin"

        jwt_token, csrf_token = create_access_token(data=token_data)

        frontend_url = settings.frontend_login_success_uri
        logger.info(f"Redirecting to frontend for {email} (registered={user.is_registered})")
        response = RedirectResponse(url=f"{frontend_url}?token={jwt_token}")
        response.set_cookie(
            key="jwt",
            value=jwt_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return response

    except Exception as e:
        await db.rollback()
        import traceback
        logger.error(f"Error processing Line auth callback: {e}\n{traceback.format_exc()}")
        return RedirectResponse(url=settings.frontend_login_failure_uri)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=100)


@router.post("/auth/register")
async def register_merchant(body: RegisterRequest,
                            db: DBSession,
                            payload: dict = Depends(get_jwt_payload)
                            ):
    """
    Complete merchant registration after Google SSO.
    Requires a valid JWT with is_registered=False.
    Creates an ADMIN staff record and marks the auth_user as registered.
    """

    if payload.get("is_registered", False):
        raise HTTPException(status_code=400, detail="Already registered")

    auth_user_id = payload.get("auth_user_id")
    store_id = payload.get("store_id")
    if not auth_user_id or not store_id:
        raise HTTPException(status_code=400, detail="Invalid token for registration")

    # Check username not taken within this store
    existing = await db.scalar(
        select(Staff).where(Staff.username == body.username, Staff.store_id == store_id)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Create admin staff record
    new_staff = Staff(
        store_id=store_id,
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=StaffRole.ADMIN,
        is_active=True,
    )
    db.add(new_staff)

    # Mark auth_user as registered
    auth_user = await db.scalar(select(AuthUser).where(AuthUser.id == auth_user_id))
    if not auth_user:
        raise HTTPException(status_code=404, detail="Auth user not found")
    auth_user.is_registered = True

    try:
        await db.commit()
        await db.refresh(new_staff)
    except Exception as e:
        await db.rollback()
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

    # Issue new JWT as admin
    jwt_token, csrf_token = create_access_token(
        data={
            "sub": str(new_staff.id),
            "auth_user_id": auth_user.id,
            "store_id": store_id,
            "is_registered": True,
            "username": new_staff.username,
            "role": "admin",
        }
    )

    response = JSONResponse(content={
        "message": "Registration successful",
        "username": new_staff.username,
        "role": "admin"
    })
    response.set_cookie(
        key="jwt",
        value=jwt_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/login/local")
async def login_local(credentials: StandardLogin, db: DBSession):
    query = select(Staff).where(Staff.username == credentials.username)
    if credentials.store_id is not None:
        query = query.where(Staff.store_id == credentials.store_id)
    staff = await db.scalar(query)
    
    if not staff or not verify_password(credentials.password, staff.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if credentials.role and staff.role.name.lower() != credentials.role.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid username or password or role"
        )

    if not staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled. Please contact a restaurant owner."
        )
    
    jwt_token, csrf_token = create_access_token(
        data={
            "sub": str(staff.id),
            "username": staff.username,
            "role": staff.role.name,
            "store_id": staff.store_id,
            "is_registered": True,
        }
    )

    response = JSONResponse(
        content={
            "message": "Login successful",
            "username": staff.username,
            "role": staff.role.name,
            "csrf_token": csrf_token
        }
    )
    
    # 5. Attach the token as a secure HttpOnly cookie
    response.set_cookie(
        key="jwt",
        value=jwt_token,
        httponly=True,
        # secure=settings.jwt_cookie_secure,
        secure=True,  # Set to True in production with HTTPS
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



@router.post("/qr/{qr_token}")
async def login_via_qr(qr_token: str, body: CustomerQRLogin, db: DBSession):
    """
    **Customer QR Code Login**

    Called when a customer scans the table QR code and submits their name.
    1. Validates the qr_token against the Tables table.
    2. Marks the table as OCCUPIED and starts a session if it was FREE.
    3. Creates a new Customer record linked to the table.
    4. Issues a JWT (HttpOnly cookie) with role='customer' and returns csrf_token.
    """
    table = await db.scalar(select(Tables).where(Tables.qr_token == qr_token))
    if not table:
        raise HTTPException(status_code=404, detail="Invalid QR code")

    now = datetime.now(BANGKOK_TZ)
    session_token = secrets.token_urlsafe(32)

    # Start a new table session if the table is currently free
    if table.status == TableStatus.FREE:
        table.status = TableStatus.PENDING
        table.session_token = session_token
        table.session_started_at = now
        table.updated_at = now
    else:
        # Reuse existing session token so all customers at the same table share one order
        session_token = table.session_token

    new_customer = Customers(
        table_id=table.id,
        store_id=table.store_id,
        session_token=session_token,
        name=body.name,
        token=secrets.token_urlsafe(32),
        is_active=True,
        updated_at=now,
    )
    db.add(new_customer)

    try:
        await db.commit()
        await db.refresh(new_customer)
    except Exception as e:
        await db.rollback()
        logger.error(f"QR login failed: {e}")
        raise HTTPException(status_code=500, detail="Could not create customer session")

    jwt_token, csrf_token = create_access_token(
        data={
            "sub": str(new_customer.id),
            "role": "customer",
            "store_id": table.store_id,
            "table_id": table.id,
            "customer_name": body.name,
        }
    )

    response = JSONResponse(content={
        "message": "Login successful",
        "customer_id": new_customer.id,
        "table_id": table.id,
        "table_number": table.number,
        "csrf_token": csrf_token,
    })
    response.set_cookie(
        key="jwt_customer",
        value=jwt_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@router.get("/logout", response_model=Message)
async def logout():
    """
    **Logout User**

    Instructs the client to clear the JWT token.
    Note: Real server-side logout would require a token blacklist.
    """
    logger.info("User logged out")
    return JSONResponse(content={"message": "Logout successful. Remove JWT token on frontend."})


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: AuthUser = Depends(get_current_user)):
    """
    **Get Current User Profile**

    Returns the profile information of the currently authenticated user.
    Requires a valid JWT token in the `jwt` cookie or Authorization header (logic depends on `get_current_user`).
    """
    logger.info(f"Fetching profile for {current_user.email}")
    return {"email": current_user.email, "name": current_user.name, "avatar_url": current_user.avatar_url}


def register_routes(router_instance: APIRouter):
    router_instance.include_router(router)
