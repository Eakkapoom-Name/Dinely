from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.utilities.auth import require_admin, require_staff, require_staff_read_only
from app.models import database_models as models
from app.schemas import schemas as schemas

from app.utilities.timezone import BANGKOK_TZ
from datetime import datetime

from app.utilities.qr_code import generate_qr_token

router = APIRouter(prefix="/api/table",
                   tags=["Tables"])


@router.post("/create",
             response_model=schemas.TableResponse,
             status_code=status.HTTP_201_CREATED)
async def create_table(
    table: schemas.TableCreate,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")

    table_number_exist = await db.scalar(select(models.Tables).where(models.Tables.number == table.number, models.Tables.store_id == store_id))

    if table_number_exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Table with number of {table.number} is already existed")

    new_table = models.Tables(**table.model_dump())
    new_table.store_id = store_id

    new_table.updated_at = datetime.now(BANGKOK_TZ)

    new_table.qr_token = generate_qr_token()

    db.add(new_table)

    try:
        await db.commit()
        await db.refresh(new_table)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create table")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return new_table


@router.get("/all_occupied",
            response_model=List[schemas.TableResponse])
async def get_occupied_table(
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.Tables).where(models.Tables.status == models.TableStatus.OCCUPIED, models.Tables.store_id == store_id))
    query_table = query_result.all()
    
    return query_table


@router.get("/all",
            response_model=List[schemas.TableResponse])
async def get_all_table(
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.Tables).where(models.Tables.store_id == store_id))
    query_tables = query_result.all()

    return query_tables


@router.get("/verify")
async def verify_qr_token(token: str, db: DBSession):
    table = await db.scalar(select(models.Tables).where(models.Tables.qr_token == token))
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid QR token")
    return {"id": table.id, "number": table.number, "status": table.status}


@router.get("/{table_id}",
            response_model=schemas.TableResponse)
async def get_table_by_id(
    table_id: int,
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    query_table = await db.scalar(select(models.Tables).where(models.Tables.id == table_id, models.Tables.store_id == store_id))

    if not query_table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no table with id of {table_id}")

    return query_table


@router.patch("/{table_id}",
              response_model=schemas.TableResponse)
async def update_table_by_id(
    table_id: int,
    update_data: schemas.TableUpdate,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    query_table = await db.scalar(select(models.Tables).where(models.Tables.id == table_id, models.Tables.store_id == store_id))

    if not query_table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no table with id of {table_id}")

    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")

    # Clear session when transitioning to FREE
    if update_data.status is not None and update_data.status == models.TableStatus.FREE:
        if query_table.status != models.TableStatus.FREE:
            update_dict["session_started_at"] = None
            update_dict["session_token"] = None

    for key, value in update_dict.items():
        setattr(query_table, key, value)

    query_table.updated_at = datetime.now(BANGKOK_TZ)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update table")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return query_table

@router.delete("/{table_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_table_by_id(
    table_id: int,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")

    query_table = await db.scalar(select(models.Tables).where(models.Tables.id == table_id, models.Tables.store_id == store_id))

    if not query_table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no table with id of {table_id}")

    try:
        await db.execute(
            update(models.Customers).where(models.Customers.table_id == table_id).values(table_id=None)
        )
        await db.execute(
            update(models.Orders).where(models.Orders.table_id == table_id).values(table_id=None)
        )
        await db.delete(query_table)
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete table")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)