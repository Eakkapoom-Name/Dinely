from fastapi import APIRouter, status, HTTPException, Response, Depends
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.utilities.auth import get_jwt_payload, require_customer, require_customer_read_only, require_staff, require_staff_read_only
from app.models import database_models as models
from app.schemas import schemas as schemas


class KitchenDoneRequest(BaseModel):
    item_ids: List[int]

router = APIRouter(prefix="/api/order_item",
                   tags=["Order Items"])


@router.post("/create",
             response_model=schemas.OrderItemResponse,
             status_code=status.HTTP_201_CREATED)
async def create_order_item(
    order_item: schemas.OrderItemCreate,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    order_id_exist = await db.scalar(select(models.Orders).where(models.Orders.id == order_item.order_id))

    if not order_id_exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no order with id {order_item.order_id}")
    
    menu_item_id_exist = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == order_item.menu_item_id,
                                                                        models.MenuItems.deleted_at.is_(None)))

    if not menu_item_id_exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no menu item with id {order_item.menu_item_id}")
    
    new_order_item = models.OrderItems(**order_item.model_dump())

    new_order_item.name = menu_item_id_exist.name

    db.add(new_order_item)

    try:
        await db.commit()
        await db.refresh(new_order_item)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create order item")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return new_order_item


@router.get("/get_order/{order_id}")
async def get_order_item_by_order_id(
    order_id: int,
    db: DBSession,
    payload: dict = Depends(get_jwt_payload)
):
    store_id = payload.get("store_id")
    order_exist = await db.scalar(select(models.Orders).where(
        models.Orders.id == order_id,
        models.Orders.store_id == store_id
    ))

    if not order_exist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no order with id {order_id}")

    query_order_items = await db.scalars(
        select(models.OrderItems).where(
            models.OrderItems.order_id == order_id
        ).options(joinedload(models.OrderItems.menu_item))
    )

    order_items = query_order_items.unique().all()

    result = []
    for item in order_items:
        image_url = None
        if item.menu_item and item.menu_item.image_url:
            image_url = item.menu_item.image_url
        result.append({
            "id": item.id,
            "order_id": item.order_id,
            "menu_item_id": item.menu_item_id,
            "name": item.name,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
            "add_ons": item.add_ons,
            "notes": item.notes,
            "kitchen_status": item.kitchen_status.value if item.kitchen_status else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "image_url": image_url
        })

    return result


@router.get("/kitchen_order")
async def get_all_kitchen_order_item(
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.OrderItems).where(
        models.OrderItems.kitchen_status == models.KitchenStatus.PREPARING,
        models.OrderItems.store_id == store_id
    ).options(joinedload(models.OrderItems.order)))

    query_order_items = query_result.unique().all()

    # Build table_id -> table_number map
    table_ids = {item.order.table_id for item in query_order_items if item.order and item.order.table_id}
    table_map = {}
    if table_ids:
        tables = await db.scalars(select(models.Tables).where(models.Tables.id.in_(table_ids)))
        table_map = {t.id: t.number for t in tables.all()}

    result = []
    for item in query_order_items:
        table_number = None
        table_id = None
        if item.order and item.order.table_id:
            table_id = item.order.table_id
            table_number = table_map.get(item.order.table_id)
        result.append({
            "id": item.id,
            "order_id": item.order_id,
            "menu_item_id": item.menu_item_id,
            "name": item.name,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
            "add_ons": item.add_ons,
            "notes": item.notes,
            "kitchen_status": item.kitchen_status.value if item.kitchen_status else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "table_id": table_id,
            "table_number": table_number
        })

    return result


@router.patch("/kitchen_done")
async def kitchen_done(
    body: KitchenDoneRequest,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    """
    Mark specified kitchen items as FINISHED.
    If ALL items for the table are now FINISHED, auto-update table to WAITING_FOR_PAYMENT.
    """
    store_id = payload.get("store_id")

    if not body.item_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No item IDs provided")

    # Fetch all specified items with their orders
    items_result = await db.scalars(
        select(models.OrderItems).where(
            models.OrderItems.id.in_(body.item_ids),
            models.OrderItems.store_id == store_id
        ).options(joinedload(models.OrderItems.order))
    )
    items = items_result.unique().all()

    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching items found")

    # Mark all as FINISHED
    table_ids = set()
    for item in items:
        item.kitchen_status = models.KitchenStatus.FINISHED
        if item.order and item.order.table_id:
            table_ids.add(item.order.table_id)

    await db.flush()

    # For each affected table, check if ANY PREPARING items remain
    for table_id in table_ids:
        remaining = await db.scalar(
            select(models.OrderItems.id).join(models.Orders).where(
                models.Orders.table_id == table_id,
                models.Orders.status == models.OrderStatus.PENDING,
                models.Orders.store_id == store_id,
                models.OrderItems.kitchen_status == models.KitchenStatus.PREPARING
            )
        )
        if remaining is None:
            # No PREPARING items left → set table to WAITING_FOR_PAYMENT
            table = await db.scalar(
                select(models.Tables).where(models.Tables.id == table_id)
            )
            if table and table.status == models.TableStatus.PREPARING:
                table.status = models.TableStatus.WAITING_FOR_PAYMENT

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return {"message": f"{len(items)} items marked as finished"}


@router.get("/all",
            response_model=List[schemas.OrderItemResponse])
async def get_all_order_item(
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.OrderItems).where(
        models.OrderItems.store_id == store_id
    ))
    query_order_items = query_result.all()

    return query_order_items


@router.get("/{order_item_id}",
            response_model=schemas.OrderItemResponse)
async def get_order_item_by_id(
    order_item_id: int,
    db: DBSession,
    payload: dict = Depends(get_jwt_payload)
):
    store_id = payload.get("store_id")
    query_order_item = await db.scalar(select(models.OrderItems).where(
        models.OrderItems.id == order_item_id,
        models.OrderItems.store_id == store_id
    ))

    if not query_order_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no order item with id {order_item_id}")

    return query_order_item


@router.patch("/status/{order_item_id}",
              response_model=schemas.OrderItemResponse)
async def update_order_item_status_by_id(
    order_item_id: int,
    updated_status: models.KitchenStatus,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    query_order_item = await db.scalar(select(models.OrderItems).where(
        models.OrderItems.id == order_item_id,
        models.OrderItems.store_id == store_id
    ))

    if not query_order_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"order item with id {order_item_id} not found")

    query_order_item.kitchen_status = updated_status

    try:
        await db.commit()
    
    except HTTPException:
        await db.rollback()
        raise

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update order item's kitchen status")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return query_order_item


@router.patch("/{order_item_id}",
              response_model=schemas.OrderItemResponse)
async def update_order_item_by_id(
    order_item_id: int,
    update_data: schemas.OrderItemUpdate,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    query_order_item = await db.scalar(select(models.OrderItems).where(
        models.OrderItems.id == order_item_id,
        models.OrderItems.store_id == store_id
    ))

    if not query_order_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no order item with id {order_item_id}")
    
    if update_data.order_id is not None:
        order_id_exist = await db.scalar(select(models.Orders).where(models.Orders.id == update_data.order_id))
        if not order_id_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no order id with id {update_data.order_id}")
        
    if update_data.menu_item_id is not None:
        menu_item_id_exist = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == update_data.menu_item_id))
        if not menu_item_id_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no menu item with id {update_data.menu_item_id}")
        
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")
    
    for key, value in update_dict.items():
        setattr(query_order_item, key, value)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update order item")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return query_order_item


@router.delete("/{order_item_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_item_by_id(
    order_item_id: int,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    query_order_item = await db.scalar(select(models.OrderItems).where(
        models.OrderItems.id == order_item_id,
        models.OrderItems.store_id == store_id
    ))

    if not query_order_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no order item with id {order_item_id}")
    
    try:
        await db.delete(query_order_item)
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete order item")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
 
    return Response(status_code=status.HTTP_204_NO_CONTENT)