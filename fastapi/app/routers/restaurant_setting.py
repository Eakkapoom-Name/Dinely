from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.utilities.auth import get_jwt_payload, require_admin
from app.models import database_models as models
from app.schemas import schemas as schemas

router = APIRouter(prefix="/api/restaurant_setting",
                   tags=["Restaurant Settings"])


@router.post("/create",
               response_model=schemas.RestaurantSettingResponse,
               status_code=status.HTTP_201_CREATED)
async def create_restaurant_setting(restaurant: schemas.RestaurantSettingCreate,
                              db: DBSession,
                              payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")
    exist = await db.scalar(select(models.RestaurantSettings).where(models.RestaurantSettings.name == restaurant.name,
                                                                     models.RestaurantSettings.store_id == store_id))

    if exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The restaurant {restaurant.name} is already existed")

    new_restaurant = models.RestaurantSettings(**restaurant.model_dump())
    new_restaurant.store_id = store_id

    db.add(new_restaurant)
    
    try:
        await db.commit()
        await db.refresh(new_restaurant)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not create restaurant {new_restaurant.name}")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return new_restaurant


@router.get("/all",
            response_model=List[schemas.RestaurantSettingResponse])
async def get_all_restaurant_setting(db: DBSession,
                                     payload: dict = Depends(get_jwt_payload)):
    store_id = payload.get("store_id")
    query_result = await db.scalars(select(models.RestaurantSettings).where(models.RestaurantSettings.store_id == store_id))
    query_restaurants = query_result.all()

    return query_restaurants


@router.get("/{restaurant_id}",
            response_model=schemas.RestaurantSettingResponse)
async def get_restaurant_setting_by_id(restaurant_id: int,
                                       db: DBSession,
                                       payload: dict = Depends(get_jwt_payload)):
    store_id = payload.get("store_id")
    query_restaurant = await db.scalar(select(models.RestaurantSettings).where(models.RestaurantSettings.id == restaurant_id,
                                                                               models.RestaurantSettings.store_id == store_id))

    if not query_restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no restaurant with the id of {restaurant_id}")
    
    return query_restaurant


@router.patch("/{restaurant_id}",
              response_model=schemas.RestaurantSettingResponse)
async def update_restaurant_setting_by_id(restaurant_id: int,
                                    update_data: schemas.RestaurantSettingUpdate,
                                    db: DBSession,
                                    payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")
    query_restaurant = await db.scalar(select(models.RestaurantSettings).where(models.RestaurantSettings.id == restaurant_id,
                                                                               models.RestaurantSettings.store_id == store_id))

    if not query_restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no restaurant with the id of {restaurant_id}")
    
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")

    for key, value in update_dict.items():
        setattr(query_restaurant, key, value)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not update restaurant {query_restaurant.name}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return query_restaurant


@router.delete("/{restaurant_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_restaurant_setting_by_id(restaurant_id: int,
                                    db: DBSession,
                                    payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")
    query_restaurant = await db.scalar(select(models.RestaurantSettings).where(models.RestaurantSettings.id == restaurant_id,
                                                                               models.RestaurantSettings.store_id == store_id))

    if not query_restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no restaurant with the id of {restaurant_id}")
    

    try:
        await db.delete(query_restaurant)
        await db.commit()
    
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not delete restaurant {query_restaurant.name}")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)