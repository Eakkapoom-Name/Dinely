from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.utilities.auth import get_jwt_payload, require_admin
from app.models import database_models as models
from app.schemas import schemas as schemas

router = APIRouter(prefix="/api/category",
                   tags=["Categories"])


@router.post("/create",
             response_model=schemas.CategoryResponse,
             status_code=status.HTTP_201_CREATED,)
async def create_category(
    cat: schemas.CategoryCreate,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")
    exist = await db.scalar(select(models.Categories).where(models.Categories.name == cat.name,
                                                             models.Categories.store_id == store_id))

    if exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Category {cat.name} is already existed")

    new_cat = models.Categories(**cat.model_dump())
    new_cat.store_id = store_id

    db.add(new_cat)

    try:
        await db.commit()
        await db.refresh(new_cat)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not create category {new_cat.name}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return new_cat


@router.get("/all",
            response_model=List[schemas.CategoryResponse])
async def get_all_category(db: DBSession,
                           payload: dict = Depends(get_jwt_payload)):
    store_id = payload.get("store_id")
    query_result = await db.scalars(select(models.Categories).where(models.Categories.store_id == store_id))
    query_cats = query_result.all()

    return query_cats


@router.get("/{cat_id}",
            response_model=schemas.CategoryResponse)
async def get_category_by_id(
    cat_id: int,
    db: DBSession,
    payload: dict = Depends(get_jwt_payload)
):
    store_id = payload.get("store_id")
    query_cat = await db.scalar(select(models.Categories).where(models.Categories.id == cat_id,
                                                                 models.Categories.store_id == store_id))

    if not query_cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no category with the id of {cat_id}")

    return query_cat


@router.patch("/{cat_id}",
              response_model=schemas.CategoryResponse)
async def update_category_by_id(
    cat_id: int,
    update_data: schemas.CategoryUpdate,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")
    query_cat = await db.scalar(select(models.Categories).where(models.Categories.id == cat_id,
                                                                 models.Categories.store_id == store_id))

    if not query_cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no category with the id of {cat_id}")

    update_dict = update_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")

    for key, value in update_dict.items():
        setattr(query_cat, key, value)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not update category {query_cat.name}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return query_cat


@router.delete("/{cat_id}",
               status_code=status.HTTP_204_NO_CONTENT,)
async def delete_category_by_id(
    cat_id: int,
    db: DBSession,
    payload: dict = Depends(require_admin)
):
    store_id = payload.get("store_id")
    query_cat = await db.scalar(select(models.Categories).where(models.Categories.id == cat_id,
                                                                 models.Categories.store_id == store_id))

    if not query_cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no category with the id of {cat_id}")

    # Check for active menu items in this category
    active_items = await db.scalar(
        select(models.MenuItems.id).where(
            models.MenuItems.category_id == cat_id,
            models.MenuItems.deleted_at.is_(None)
        )
    )
    if active_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category '{query_cat.name}' because it still has active menu items. Remove or reassign them first."
        )

    try:
        await db.delete(query_cat)
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not delete category {query_cat.name}")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
