from fastapi import APIRouter, UploadFile, File, status, HTTPException, Response, Depends
from app.utilities.upload import upload_image_to_supabase
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from datetime import datetime
from typing import List

from app.db import DBSession
from app.utilities.auth import get_jwt_payload, require_admin, require_kitchen
from app.models import database_models as models
from app.schemas import schemas as schemas
from app.utilities.timezone import BANGKOK_TZ

router = APIRouter(prefix="/api/menu_item",
                   tags=["Menu Items"])


@router.post("/create",
             response_model=schemas.MenuItemResponse,
             status_code=status.HTTP_201_CREATED)
async def create_menu_item(item: schemas.MenuItemCreate,
                     db: DBSession,
                     payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")
    exist = await db.scalar(select(models.MenuItems).where(models.MenuItems.name == item.name,
                                                           models.MenuItems.deleted_at.is_(None),
                                                           models.MenuItems.store_id == store_id))

    if exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The menu {item.name} is already existed")
    
    if item.category_id is not None:
        check_cat_id = await db.scalar(select(models.Categories).where(models.Categories.id == item.category_id,
                                                                        models.Categories.store_id == store_id))
        if not check_cat_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no category with id of {item.category_id}")

    new_item = models.MenuItems(**item.model_dump())
    new_item.store_id = store_id

    db.add(new_item)

    try:
        await db.commit()
        await db.refresh(new_item)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not create item {new_item.name}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return new_item

    
@router.post("/upload_image")
async def upload_menu_image(file: UploadFile = File(...),
                            payload: dict = Depends(require_admin)):
    url = await upload_image_to_supabase(file)
    return {"image_url": url}


@router.get("/all",
            response_model=List[schemas.MenuItemResponse])
async def get_all_menu_item(db: DBSession,
                            payload: dict = Depends(get_jwt_payload)):
    store_id = payload.get("store_id")
    query_result = await db.scalars(select(models.MenuItems).where(models.MenuItems.deleted_at.is_(None),
                                                                    models.MenuItems.store_id == store_id))
    query_menu_items = query_result.all()

    return query_menu_items


@router.get("/{item_id}",
            response_model=schemas.MenuItemResponse)
async def get_menu_item_by_id(item_id: int,
                              db: DBSession,
                              payload: dict = Depends(get_jwt_payload)):
    store_id = payload.get("store_id")
    query_item = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == item_id,
                                                                models.MenuItems.deleted_at.is_(None),
                                                                models.MenuItems.store_id == store_id))

    if not query_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"there is no item with the id of {item_id}")
    
    return query_item


@router.patch("/{item_id}",
              response_model=schemas.MenuItemResponse)
async def update_menu_item_by_id(item_id: int,
                           update_data: schemas.MenuItemUpdate,
                           db: DBSession,
                           payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")
    query_item = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == item_id,
                                                                models.MenuItems.deleted_at.is_(None),
                                                                models.MenuItems.store_id == store_id))

    if not query_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"there is no item with the id of {item_id}")
    
    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")

    for key, value in update_dict.items():
        if key == "category_id":
            check_category_id = await db.scalar(select(models.Categories).where(models.Categories.id == value,
                                                                                models.Categories.store_id == store_id))
            if not check_category_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no category with id of {value}")
            else:
                setattr(query_item, key, value)

        else:
            setattr(query_item, key, value)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not update item {query_item.name}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return query_item


@router.patch("/{item_id}/availability",
              response_model=schemas.MenuItemResponse)
async def toggle_menu_item_availability(item_id: int,
                           db: DBSession,
                           payload: dict = Depends(require_kitchen)):
    store_id = payload.get("store_id")
    query_item = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == item_id,
                                                                models.MenuItems.deleted_at.is_(None),
                                                                models.MenuItems.store_id == store_id))

    if not query_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"there is no item with the id of {item_id}")

    query_item.available = not query_item.available

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return query_item


@router.patch("/{item_id}/addon_availability")
async def toggle_addon_availability(
    item_id: int,
    body: dict,
    db: DBSession,
    payload: dict = Depends(require_kitchen)
):
    store_id = payload.get("store_id")
    addon_name = body.get("addon_name")
    enabled = body.get("enabled")

    if addon_name is None or enabled is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="addon_name and enabled are required")

    query_item = await db.scalar(select(models.MenuItems).where(
        models.MenuItems.id == item_id,
        models.MenuItems.deleted_at.is_(None),
        models.MenuItems.store_id == store_id
    ))

    if not query_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"there is no item with the id of {item_id}")

    add_ons = dict(query_item.add_ons or {})
    disabled_add_ons = dict(query_item.disabled_add_ons or {})

    if enabled:
        # Move from disabled_add_ons to add_ons
        if addon_name in disabled_add_ons:
            add_ons[addon_name] = disabled_add_ons.pop(addon_name)
    else:
        # Move from add_ons to disabled_add_ons
        if addon_name in add_ons:
            disabled_add_ons[addon_name] = add_ons.pop(addon_name)

    query_item.add_ons = add_ons
    query_item.disabled_add_ons = disabled_add_ons

    try:
        await db.commit()
        await db.refresh(query_item)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return {"add_ons": query_item.add_ons, "disabled_add_ons": query_item.disabled_add_ons}


@router.delete("/{item_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item_by_id(item_id: int,
                           db: DBSession,
                           payload: dict = Depends(require_admin)):
    store_id = payload.get("store_id")
    query_item = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == item_id,
                                                                models.MenuItems.deleted_at.is_(None),
                                                                models.MenuItems.store_id == store_id))

    if not query_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"there is no item with the id of {item_id}")
    
    query_item.deleted_at = datetime.now(BANGKOK_TZ)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not delete item {query_item.name}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)