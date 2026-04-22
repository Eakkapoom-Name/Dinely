from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.utilities.auth import require_admin_read_only, require_admin, require_staff
from app.models import database_models as models
from app.schemas import schemas as schemas

from app.utilities.timezone import BANGKOK_TZ
from datetime import datetime, date

router = APIRouter(prefix="/api/daily_item_performance",
                   tags=["Daily Item Performance"])


async def create_daily_item_performance(
    item_performance: schemas.DailyItemPerformanceMake,
    menu_item: models.MenuItems,
    db: DBSession,
    current_date: date,
    store_id: int = None
):
    revenue = menu_item.price * item_performance.quantity_sold

    new_item = models.DailyItemPerformance(
        date=current_date,
        menu_item_id=menu_item.id,
        quantity_sold=item_performance.quantity_sold,
        gross_revenue=revenue
    )
    new_item.store_id = store_id

    db.add(new_item)

    return new_item
    

async def update_daily_item_performance(
    update_data: schemas.DailyItemPerformanceMake,
    query_item: models.DailyItemPerformance,
    menu_item: models.MenuItems
):
    query_item.quantity_sold += update_data.quantity_sold
    query_item.gross_revenue = menu_item.price * query_item.quantity_sold

    return query_item


async def item_performance_make_decider(
    item_data: schemas.DailyItemPerformanceMake,
    db: DBSession,
    store_id: int = None
):
    menu_item = await db.scalar(select(models.MenuItems).where(
        models.MenuItems.id == item_data.menu_item_id
    ))

    if not menu_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no menu item with id {item_data.menu_item_id}")

    today_date = datetime.now(BANGKOK_TZ).date()

    item_performance_exist = await db.scalar(select(models.DailyItemPerformance).where(
        models.DailyItemPerformance.date == today_date,
        models.DailyItemPerformance.menu_item_id == item_data.menu_item_id,
        models.DailyItemPerformance.store_id == store_id
    ))

    if not item_performance_exist:
        return await create_daily_item_performance(
            item_performance=item_data,
            menu_item=menu_item,
            db=db,
            current_date=today_date,
            store_id=store_id
        )

    else:
        #update
        return await update_daily_item_performance(
            update_data=item_data,
            query_item=item_performance_exist,
            menu_item=menu_item
        )

@router.post("/make")
async def make_daily_item_performance(
    item_data: schemas.DailyItemPerformanceMake,
    db: DBSession,
    response: Response,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    menu_item = await db.scalar(select(models.MenuItems).where(
        models.MenuItems.id == item_data.menu_item_id
    ))

    if not menu_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no menu item with id {item_data.menu_item_id}")

    today_date = datetime.now(BANGKOK_TZ).date()

    item_performance_exist = await db.scalar(select(models.DailyItemPerformance).where(
        models.DailyItemPerformance.date == today_date,
        models.DailyItemPerformance.menu_item_id == item_data.menu_item_id,
        models.DailyItemPerformance.store_id == store_id
    ))

    if not item_performance_exist:
        #create
        result_item = await create_daily_item_performance(
            item_performance=item_data,
            menu_item=menu_item,
            db=db,
            current_date=today_date,
            store_id=store_id
        )
        response.status_code = status.HTTP_201_CREATED

    else:
        #update
        result_item = await update_daily_item_performance(
            update_data=item_data,
            query_item=item_performance_exist,
            menu_item=menu_item
        )
        response.status_code = status.HTTP_200_OK

    try:
        await db.commit()
        await db.refresh(result_item)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update daily item performance")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return {
        "message": "make item's performance successfully"
    }


@router.get("/all",
            response_model=List[schemas.DailyItemPerformanceResponse])
async def get_all_daily_item_performace(
    db: DBSession,
    payload: dict = Depends(require_admin_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.DailyItemPerformance).where(
        models.DailyItemPerformance.store_id == store_id
    ).options(
        joinedload(models.DailyItemPerformance.menu_item)
    ))
    query_items = query_result.all()

    return query_items


# item_id = menu_item_id (daily item performace dont have id)
@router.get("/all_time/{item_id}",
            response_model=List[schemas.DailyItemPerformanceResponse])
async def get_all_time_daily_item_performance_by_id(
    item_id: int,
    db: DBSession,
    payload: dict = Depends(require_admin_read_only)
):
    menu_item_exist = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == item_id))

    if not menu_item_exist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no menu item with id {item_id}")
    
    store_id = payload.get("store_id")

    all_time_query = await db.scalars(select(models.DailyItemPerformance).where(
        models.DailyItemPerformance.menu_item_id == item_id,
        models.DailyItemPerformance.store_id == store_id
    ).options(
        joinedload(models.DailyItemPerformance.menu_item)
    ))

    if not all_time_query:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no data of menu item with id {item_id}'s daily performance")

    all_time_daily_performance = all_time_query.all()

    return all_time_daily_performance


@router.delete("/range",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_daily_item_performance_by_range(
    start_date: date,
    end_date: date,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")

    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be before or equal to end_date")

    try:
        await db.execute(
            delete(models.DailyItemPerformance).where(
                models.DailyItemPerformance.store_id == store_id,
                models.DailyItemPerformance.date >= start_date,
                models.DailyItemPerformance.date <= end_date
            )
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)