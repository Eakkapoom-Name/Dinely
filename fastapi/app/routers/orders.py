from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select, delete, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from decimal import Decimal
from typing import List

from app.db import DBSession
from app.models import database_models as models
from app.schemas import schemas as schemas
from app.routers.daily_item_performance import item_performance_make_decider
from app.routers.daily_business_stats import business_stat_make_decider

from app.utilities.timezone import BANGKOK_TZ
from app.utilities.auth import require_customer, require_customer_read_only, require_staff, require_admin, require_staff_read_only, get_jwt_payload
from datetime import datetime

router = APIRouter(prefix="/api/order",
                   tags=["Orders"])


@router.post("/make/{customer_id}")
async def make_order_by_customer_id(
    customer_id: int,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    customer = await db.scalar(select(models.Customers).where(models.Customers.id == customer_id))

    if not customer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no customer with id {customer_id}")

    table = await db.scalar(select(models.Tables).where(models.Tables.id == customer.table_id))

    if not table:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid table id {customer.table_id}")

    if table.session_token is None:
        table.session_token = customer.session_token

    query_cart_items = await db.scalars(select(models.CartItems).where(
        models.CartItems.customer_id == customer_id).options(joinedload(models.CartItems.menu_item)))

    cart_items = query_cart_items.all()

    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no cart item for customer with id {customer_id}")

    current_datetime = datetime.now(BANGKOK_TZ)

    try:
        ## check if the order of this table already existed?
        order = await db.scalar(select(models.Orders).where(
            models.Orders.table_id == table.id,
            models.Orders.status == models.OrderStatus.PENDING,
            models.Orders.session_token == table.session_token).options(
                joinedload(models.Orders.order_items)
            ))
        
        if not order:
            new_order = models.Orders(
                table_id=table.id,
                session_token=table.session_token,
                customer_id=customer_id,
                customer_name=customer.name,
                status=models.OrderStatus.PENDING,
                created_at=current_datetime,
                updated_at=current_datetime,
                is_paid=False
            )
            new_order.store_id = table.store_id

            db.add(new_order)
            await db.flush()

            active_order = new_order

        else:
            active_order = order

        for citem in cart_items:
            menu_item = citem.menu_item

            if menu_item.deleted_at is not None or menu_item.available is False:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sorry {menu_item.name} is no longer available")

            if menu_item.stock_enabled:
                if citem.quantity > menu_item.stock_quantity:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sorry, only have {menu_item.stock_quantity} of {menu_item.name} left")

                menu_item.stock_quantity -= citem.quantity

            existing_order_item = await db.scalar(
                select(models.OrderItems).where(
                    models.OrderItems.order_id == active_order.id,
                    models.OrderItems.menu_item_id == menu_item.id,
                    models.OrderItems.notes == citem.notes,
                    models.OrderItems.add_ons == citem.add_ons,
                    models.OrderItems.kitchen_status == models.KitchenStatus.PREPARING,
                )
            )

            if existing_order_item:
                existing_order_item.quantity += citem.quantity
            else:
                order_item = models.OrderItems(
                    order_id=active_order.id,
                    menu_item_id=menu_item.id,
                    name=menu_item.name,
                    quantity=citem.quantity,
                    unit_price=menu_item.price,
                    add_ons=citem.add_ons,
                    notes=citem.notes,
                    kitchen_status=models.KitchenStatus.PREPARING,
                    created_at=datetime.now(BANGKOK_TZ)
                )
                order_item.store_id = table.store_id
                db.add(order_item)

        await db.execute(delete(models.CartItems).where(models.CartItems.customer_id == customer_id))

        # Set table to PREPARING when order is placed
        table.status = models.TableStatus.PREPARING
        table.updated_at = datetime.now(BANGKOK_TZ)

        await db.commit()

        return {
            "message": "Order placed successfully",
            "order_id": active_order.id
        }

    except HTTPException:
        await db.rollback()
        raise

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not make the order")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")


@router.post("/checkout/{table_id}")
async def order_checkout(
    table_id: int,
    num_of_customer: int,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    table = await db.scalar(select(models.Tables).where(
        models.Tables.id == table_id,
        models.Tables.store_id == store_id
    ))

    if not table:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid table id : {table_id}")

    if table.status == models.TableStatus.FREE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This table is currently free")

    if table.status != models.TableStatus.WAITING_FOR_PAYMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Table must be in 'Waiting for Payment' status to checkout")

    customers_q = await db.scalars(select(models.Customers).where(models.Customers.table_id == table_id,
                                                              models.Customers.is_active.is_(True)))

    customers = customers_q.all()

    if not customers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No customer on this table at the moment")
    
    
    order = await db.scalar(select(models.Orders).where(
        models.Orders.table_id == table_id,
        models.Orders.session_token == table.session_token,
        models.Orders.status == models.OrderStatus.PENDING
    ))

    if not order:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no active order for table {table_id}")
    
    q_order_items = await db.scalars(select(models.OrderItems).where(models.OrderItems.order_id == order.id))
    order_items = q_order_items.all()
    
    current_datetime = datetime.now(BANGKOK_TZ)

    try:
        revenue = Decimal("0")

        # get item performance
        for item in order_items:
            item_total_price = item.unit_price
            
            if item.add_ons:
                for name, price in item.add_ons.items():
                    try:
                        item_total_price += Decimal(str(price))
                    except (ValueError, TypeError):
                        continue

            revenue += (item_total_price * item.quantity)

            if item.menu_item_id is not None:
                performance_data = schemas.DailyItemPerformanceMake(
                    menu_item_id=item.menu_item_id,
                    quantity_sold=item.quantity
                )

                await item_performance_make_decider(
                    item_data=performance_data,
                    db=db,
                    store_id=store_id
                )

        # get overall stat
        stats = schemas.DailyBusinessStatsMake(
            total_revenue=revenue,
            total_orders=1,
            completed_orders=1,
            cancelled_orders=0,
            total_customers=num_of_customer
        )

        await business_stat_make_decider(
            stat=stats,
            db=db,
            store_id=store_id
        )

        # compute order_number from total orders in stats
        total_orders_sum = await db.scalar(
            select(func.coalesce(func.sum(models.DailyBusinessStats.total_orders), 0)).where(
                models.DailyBusinessStats.store_id == store_id
            )
        )
        order.order_number = max(int(total_orders_sum), 1)

        # update table
        table.status = models.TableStatus.FREE
        table.session_token = None
        table.session_started_at = None
        table.updated_at = current_datetime

        # update customers (deactivate all customers at this table)
        for c in customers:
            c.is_active = False
            c.updated_at = current_datetime

        # update order
        order.status = models.OrderStatus.PAID
        order.updated_at = current_datetime
        order.is_paid = True

        await db.commit()

    except HTTPException:
        await db.rollback()
        raise

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not checkout")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return {
        "message": "Checkout successfully",
        "order_number": order.order_number
    }


@router.get("/history",
            response_model=List[schemas.OrderResponseWithOrderItem])
async def get_order_history(
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    result = await db.scalars(
        select(models.Orders).where(
            models.Orders.store_id == store_id,
            models.Orders.status == models.OrderStatus.PAID
        ).options(
            joinedload(models.Orders.order_items)
        ).order_by(models.Orders.updated_at.desc()).limit(10)
    )

    return result.unique().all()


@router.get("/get_table_price/{table_id}")
async def get_order_price_by_table_id(
    table_id: int,
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    table = await db.scalar(select(models.Tables).where(
        models.Tables.id == table_id,
        models.Tables.store_id == store_id
    ))

    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    order = await db.scalar(select(models.Orders).where(
        models.Orders.table_id == table_id,
        models.Orders.status == models.OrderStatus.PENDING).options(
            joinedload(models.Orders.order_items)
        ))

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending order for this table")

    settings = await db.scalar(select(models.RestaurantSettings).where(models.RestaurantSettings.store_id == store_id))

    if settings:
        service_charge_pct = settings.service_charge_pct
        tax_pct = settings.tax_pct
    else:
        service_charge_pct = Decimal("0")
        tax_pct = Decimal("0")

    sub_total = Decimal("0")
    for item in order.order_items:
        item_price = item.unit_price or Decimal("0")

        if item.add_ons:
            for name, price in item.add_ons.items():
                try:
                    item_price += Decimal(str(price))
                except (ValueError, TypeError):
                    continue

        sub_total += (item_price * item.quantity)

    service_charge = (sub_total * service_charge_pct) / Decimal("100")

    tax = ((sub_total + service_charge) * tax_pct) / Decimal("100")

    grand_total = sub_total + service_charge + tax

    return {
        "order_id": order.id,
        "total_table_price": str(grand_total)
    }


@router.get("/get_table/{table_id}",
            response_model=List[schemas.OrderResponseWithOrderItem])
async def get_order_by_table_id(
    table_id: int,
    db: DBSession,
    payload: dict = Depends(get_jwt_payload)
):
    store_id = payload.get("store_id")
    query_result = await db.scalars(select(models.Orders).where(
        models.Orders.table_id == table_id,
        models.Orders.store_id == store_id,
        models.Orders.status == models.OrderStatus.PENDING).options(
            joinedload(models.Orders.order_items)))

    query_orders = query_result.unique().all()

    return query_orders
    

@router.get("/get_customer/{customer_id}",
            response_model=List[schemas.OrderResponseWithOrderItem])
async def get_order_by_customer_id(
    customer_id: int,
    db: DBSession,
    payload: dict = Depends(get_jwt_payload)
):
    store_id = payload.get("store_id")
    query_result = await db.scalars(select(models.Orders).where(
        models.Orders.customer_id == customer_id,
        models.Orders.store_id == store_id).options(
            joinedload(models.Orders.order_items)))
    query_orders = query_result.unique().all()

    return query_orders


@router.get("/all",
            response_model=List[schemas.OrderResponse])
async def get_all_order(
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.Orders).where(
        models.Orders.store_id == store_id
    ))
    query_orders = query_result.all()

    return query_orders


@router.get("/{order_id}",
            response_model=schemas.OrderResponse)
async def get_order_by_id(
    order_id: int,
    db: DBSession,
    payload: dict = Depends(get_jwt_payload)
):
    store_id = payload.get("store_id")
    query_order = await db.scalar(select(models.Orders).where(
        models.Orders.id == order_id,
        models.Orders.store_id == store_id
    ))

    if not query_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no order with id {order_id}")

    return query_order


@router.patch("/cancel/{order_id}")
async def cancel_order_by_id(
    order_id: int,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    query_order = await db.scalar(select(models.Orders).where(
        models.Orders.id == order_id,
        models.Orders.store_id == store_id
    ).options(
            joinedload(models.Orders.order_items)
        ))

    if not query_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    query_order.status = models.OrderStatus.CANCELLED
    query_order.updated_at = datetime.now(BANGKOK_TZ)

    for item in query_order.order_items:
        item.kitchen_status = models.KitchenStatus.CANCELLED

    try:
        await db.commit()

    except HTTPException:
        await db.rollback()
        raise

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not cancel order")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return {
        "message": "Order is cancelled"
    }


@router.patch("/{order_id}",
              response_model=schemas.OrderResponse)
async def update_order_by_id(
    order_id: int,
    update_data: schemas.OrderUpdate,
    db: DBSession,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    query_order = await db.scalar(select(models.Orders).where(
        models.Orders.id == order_id,
        models.Orders.store_id == store_id
    ))

    if not query_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no order with id {order_id}")
    
    if update_data.table_id is not None:
        table_id_exist = await db.scalar(select(models.Tables).where(models.Tables.id == update_data.table_id))
        if not table_id_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no table with id {update_data.table_id}")
        

    if update_data.customer_id is not None:
        customer_id_exist = await db.scalar(select(models.Customers).where(models.Customers.id == update_data.customer_id))
        if not customer_id_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no customer with id {update_data.customer_id}")


    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")
    
    for key, value in update_dict.items():
        setattr(query_order, key, value)

    query_order.updated_at = datetime.now(BANGKOK_TZ)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update order")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return query_order


@router.delete("/{order_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_by_id(
    order_id: int,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")

    query_order = await db.scalar(select(models.Orders).where(
        models.Orders.id == order_id,
        models.Orders.store_id == store_id
    ))

    if not query_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no order with id {order_id}")
    
    try:
        await db.delete(query_order)
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete order")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)