from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from decimal import Decimal
from typing import List

from app.db import DBSession
from app.utilities.auth import require_admin_read_only, require_admin, require_staff
from app.models import database_models as models
from app.schemas import schemas as schemas

from app.utilities.timezone import BANGKOK_TZ
from datetime import datetime, date

router = APIRouter(prefix="/api/daily_business_stats",
                   tags=["Daily Business Stats"])


async def create_daily_business_stat(
    stat: schemas.DailyBusinessStatsMake,
    db: DBSession,
    store_id: int = None
):
    avg_value = Decimal("0") if stat.total_orders == 0 else Decimal(str(stat.total_revenue)) / stat.total_orders

    new_stat = models.DailyBusinessStats(
        **stat.model_dump(),
        date=datetime.now(BANGKOK_TZ).date(),
        updated_at=datetime.now(BANGKOK_TZ),
        average_order_value=avg_value.quantize(Decimal("0.01"))
    )
    new_stat.store_id = store_id

    db.add(new_stat)

    return new_stat


async def update_daily_business_stat(
    update_data: schemas.DailyBusinessStatsMake,
    db: DBSession,
    query_stat: models.DailyBusinessStats
):
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")
    
    for key, value in update_dict.items():
        old_value = getattr(query_stat, key)

        if old_value is None:
            setattr(query_stat, key, value)

        else:
            setattr(query_stat, key, old_value + value)

    avg_value = Decimal("0") if query_stat.total_orders == 0 else Decimal(str(query_stat.total_revenue)) / query_stat.total_orders

    query_stat.updated_at = datetime.now(BANGKOK_TZ)
    query_stat.average_order_value = avg_value.quantize(Decimal("0.01"))

    
    return query_stat


async def business_stat_make_decider(
    stat: schemas.DailyBusinessStatsMake,
    db: DBSession,
    store_id: int = None
):
    current_date = datetime.now(BANGKOK_TZ).date()

    stats_exist = await db.scalar(select(models.DailyBusinessStats).where(
        models.DailyBusinessStats.date == current_date,
        models.DailyBusinessStats.store_id == store_id
    ))

    if stats_exist is not None:
        return await update_daily_business_stat(
            update_data=stat,
            db=db,
            query_stat=stats_exist
        )

    else:
        return await create_daily_business_stat(
            stat=stat,
            db=db,
            store_id=store_id
        )


@router.post("/make",
             response_model=schemas.DailyBusinessStatsResponse)
async def make_daily_business_stat(
    stat: schemas.DailyBusinessStatsMake,
    db: DBSession,
    response: Response,
    payload: dict = Depends(require_staff)
):
    store_id = payload.get("store_id")

    current_date = datetime.now(BANGKOK_TZ).date()

    stats_exist = await db.scalar(select(models.DailyBusinessStats).where(
        models.DailyBusinessStats.date == current_date,
        models.DailyBusinessStats.store_id == store_id
    ))

    if stats_exist is not None:
        result_stat = await update_daily_business_stat(
            update_data=stat,
            db=db,
            query_stat=stats_exist
        )
        response.status_code = status.HTTP_200_OK

    else:
        result_stat = await create_daily_business_stat(
            stat=stat,
            db=db,
            store_id=store_id
        )
        response.status_code = status.HTTP_201_CREATED

    try:
        await db.commit()
        await db.refresh(result_stat)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update daily stats")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return result_stat


@router.get("/all",
            response_model=List[schemas.DailyBusinessStatsResponse])
async def get_all_daily_business_stat(
    db: DBSession,
    payload: dict = Depends(require_admin_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.DailyBusinessStats).where(
        models.DailyBusinessStats.store_id == store_id
    ))
    all_time_daily_stat = query_result.all()

    return all_time_daily_stat


# THIS FUNCTION USE QUERY PARAMETER INSTEAD
# USE /api/daily_business_stats/date/?tf_date=YYYY-MM-DD
@router.get("/date/",
            response_model=schemas.DailyBusinessStatsResponse)
async def get_daily_business_stat_by_date(
    tf_date: date,
    db: DBSession,
    payload: dict = Depends(require_admin_read_only)
):
    store_id = payload.get("store_id")

    query_stat = await db.scalar(select(models.DailyBusinessStats).where(
        models.DailyBusinessStats.date == tf_date,
        models.DailyBusinessStats.store_id == store_id
    ))

    if not query_stat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Daily business stats of date {tf_date} is not existed")

    return query_stat


@router.delete("/range",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_daily_business_stats_by_range(
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
            delete(models.DailyBusinessStats).where(
                models.DailyBusinessStats.store_id == store_id,
                models.DailyBusinessStats.date >= start_date,
                models.DailyBusinessStats.date <= end_date
            )
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)