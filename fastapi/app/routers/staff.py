from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.models import database_models as models
from app.models.authuser import AuthUser
from app.schemas import schemas as schemas
from app.utilities.security import hash_password
from app.utilities.auth import require_admin, require_admin_read_only

router = APIRouter(prefix="/api/staff",
                   tags=["Staff"])


async def get_owner_staff_id(db, store_id: int) -> int | None:
    """Find the owner's staff ID by tracing Store → AuthUser → first Staff."""
    store = await db.scalar(select(models.Store).where(models.Store.id == store_id))
    if not store or not store.owner_email:
        return None
    auth_user = await db.scalar(
        select(AuthUser).where(
            AuthUser.email == store.owner_email,
            AuthUser.is_registered == True
        )
    )
    if not auth_user:
        return None
    owner_staff = await db.scalar(
        select(models.Staff).where(
            models.Staff.store_id == store_id
        ).order_by(models.Staff.id)
    )
    return owner_staff.id if owner_staff else None


@router.post("/create",
             response_model=schemas.StaffResponse,
             status_code=status.HTTP_201_CREATED)
async def create_staff(staff: schemas.StaffCreate,
                 db: DBSession,
                 payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")

    exist = await db.scalar(select(models.Staff).where(models.Staff.username == staff.username, models.Staff.store_id == store_id))

    if exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Staff with the username of {staff.username} is already existed")

    hashed_password = hash_password(staff.password)

    staff_data = staff.model_dump(exclude={"password"})
    staff_data["password_hash"] = hashed_password

    new_staff = models.Staff(**staff_data)
    new_staff.store_id = store_id

    db.add(new_staff)

    try:
        await db.commit()
        await db.refresh(new_staff)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not create staff {new_staff.username}")
 
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return new_staff

@router.get("/all")
async def get_all_staff(db: DBSession,
                        payload: dict = Depends(require_admin_read_only)):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.Staff).where(models.Staff.store_id == store_id))
    query_staff = query_result.all()

    owner_id = await get_owner_staff_id(db, store_id)
    caller_id = int(payload.get("sub"))
    is_caller_owner = caller_id == owner_id

    result = []
    for s in query_staff:
        data = schemas.StaffResponse.model_validate(s).model_dump()
        data["is_owner"] = s.id == owner_id
        # Owner can edit everyone; non-owner admins can only edit non-admins or themselves
        if is_caller_owner:
            data["can_edit"] = True
        elif s.id == caller_id:
            data["can_edit"] = True
        elif s.role == models.StaffRole.ADMIN:
            data["can_edit"] = False
        else:
            data["can_edit"] = True
        result.append(data)

    return result


@router.get("/has_admin")
async def has_admin(db: DBSession):
    admin = await db.scalar(
        select(models.Staff).where(models.Staff.role == models.StaffRole.ADMIN)
    )
    return {"has_admin": admin is not None}


@router.post("/setup",
             response_model=schemas.StaffResponse,
             status_code=status.HTTP_201_CREATED)
async def setup_first_admin(staff: schemas.StaffCreate, db: DBSession):
    existing = await db.scalar(
        select(models.Staff).where(models.Staff.role == models.StaffRole.ADMIN)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin already exists"
        )

    hashed_password = hash_password(staff.password)
    staff_data = staff.model_dump(exclude={"password", "role"})
    staff_data["password_hash"] = hashed_password
    staff_data["role"] = models.StaffRole.ADMIN

    new_staff = models.Staff(**staff_data)
    db.add(new_staff)

    try:
        await db.commit()
        await db.refresh(new_staff)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Could not create admin")

    return new_staff


@router.get("/{staff_id}")
async def get_staff_by_id(staff_id: int,
                    db: DBSession,
                    payload: dict = Depends(require_admin_read_only)):
    store_id = payload.get("store_id")

    query_staff = await db.scalar(select(models.Staff).where(models.Staff.id == staff_id, models.Staff.store_id == store_id))

    if not query_staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no staff with the id of {staff_id}")

    owner_id = await get_owner_staff_id(db, store_id)

    return {**schemas.StaffResponse.model_validate(query_staff).model_dump(), "is_owner": query_staff.id == owner_id}


@router.patch("/{staff_id}")
async def update_staff_by_id(staff_id: int,
                       update_data: schemas.StaffUpdate,
                       db: DBSession,
                       payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")

    query_staff = await db.scalar(select(models.Staff).where(models.Staff.id == staff_id, models.Staff.store_id == store_id))

    if not query_staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no staff with the id of {staff_id}")

    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")

    owner_id = await get_owner_staff_id(db, store_id)
    caller_id = int(payload.get("sub"))
    is_caller_owner = caller_id == owner_id

    if staff_id == owner_id:
        if "role" in update_dict:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot change the role of the store owner")
        if "is_active" in update_dict and not update_dict["is_active"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot deactivate the store owner")

    # Non-owner admins cannot edit other admins
    if not is_caller_owner and staff_id != caller_id and query_staff.role == models.StaffRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the store owner can edit other admins")

    for key, value in update_dict.items():
        if key == "password":
            hashed_password = hash_password(value)
            setattr(query_staff, "password_hash", hashed_password)
        else:
            setattr(query_staff, key, value)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not update staff {query_staff.username}")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return query_staff


@router.delete("/{staff_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff_by_id(staff_id: int,
                       db: DBSession,
                       payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")

    query_staff = await db.scalar(select(models.Staff).where(models.Staff.id == staff_id, models.Staff.store_id == store_id))

    if not query_staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no staff with the id of {staff_id}")

    owner_id = await get_owner_staff_id(db, store_id)
    if staff_id == owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete the store owner")

    caller_id = int(payload.get("sub"))
    is_caller_owner = caller_id == owner_id
    if not is_caller_owner and query_staff.role == models.StaffRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the store owner can delete other admins")

    try:
        await db.delete(query_staff)
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not delete staff {query_staff.username}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
