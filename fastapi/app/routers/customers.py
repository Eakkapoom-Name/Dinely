from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.models import database_models as models
from app.schemas import schemas as schemas

from app.utilities.timezone import BANGKOK_TZ
from app.utilities.auth import require_customer, require_customer_read_only, require_admin, require_admin_read_only
from datetime import datetime

router = APIRouter(prefix="/api/customer",
                   tags=["Customers"])


@router.post("/create",
             response_model=schemas.CustomerResponse,
             status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: schemas.CustomerCreate,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    table_id_exist = await db.scalar(select(models.Tables).where(models.Tables.id == customer.table_id))

    if not table_id_exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no table with id of {customer.table_id}")

    new_customer = models.Customers(**customer.model_dump())
    new_customer.store_id = table_id_exist.store_id
    new_customer.updated_at = datetime.now(BANGKOK_TZ)

    db.add(new_customer)

    try:
        await db.commit()
        await db.refresh(new_customer)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create customer")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return new_customer   


@router.get("/all",
            response_model=List[schemas.CustomerResponse])
async def get_all_customer(
    db: DBSession,
    payload: dict = Depends(require_admin_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.Customers).where(
        models.Customers.store_id == store_id
    ))
    query_customers = query_result.all()

    return query_customers


@router.get("/me")
async def get_current_customer(
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    customer_id = int(payload.get("sub", 0))
    customer = await db.scalar(select(models.Customers).where(models.Customers.id == customer_id))
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    table = await db.scalar(select(models.Tables).where(models.Tables.id == customer.table_id))

    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "table_id": customer.table_id,
        "table_number": table.number if table else None,
    }


@router.get("/{customer_id}",
            response_model=schemas.CustomerResponse)
async def get_customer_by_id(
    customer_id: int,
    db: DBSession,
    payload: dict = Depends(require_admin_read_only)
):
    store_id = payload.get("store_id")

    query_customer = await db.scalar(select(models.Customers).where(
        models.Customers.id == customer_id,
        models.Customers.store_id == store_id
    ))

    if not query_customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no customer with id of {customer_id}")
    
    return query_customer


@router.patch("/{customer_id}",
              response_model=schemas.CustomerResponse)
async def update_customer_by_id(
    customer_id: int,
    update_data: schemas.CustomerUpdate,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")

    query_customer = await db.scalar(select(models.Customers).where(
        models.Customers.id == customer_id,
        models.Customers.store_id == store_id
    ))

    if not query_customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no customer with id of {customer_id}")

    if update_data.table_id is not None:
        table_id_exist = await db.scalar(select(models.Tables).where(models.Tables.id == update_data.table_id))
        if not table_id_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no table with id of {update_data.table_id}")
        
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")

    for key, value in update_dict.items():
        setattr(query_customer, key, value)

    query_customer.updated_at = datetime.now(BANGKOK_TZ)

    try:
        await db.commit()
        await db.refresh(query_customer)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update customer")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return query_customer


@router.delete("/{customer_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_by_id(
    customer_id: int,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")

    query_customer = await db.scalar(select(models.Customers).where(
        models.Customers.id == customer_id,
        models.Customers.store_id == store_id
    ))

    if not query_customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no customer with id {customer_id}")
    
    try:
        await db.delete(query_customer)
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete customer")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)