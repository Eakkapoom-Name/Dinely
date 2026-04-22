from fastapi import APIRouter, status, HTTPException, Response, Depends

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from typing import List

from app.db import DBSession
from app.models import database_models as models
from app.schemas import schemas as schemas
from app.utilities.auth import require_customer, require_customer_read_only, require_staff_read_only, get_jwt_payload

router = APIRouter(prefix="/api/cart_item",
                   tags=["Cart Items"])


@router.post("/create",
             response_model=schemas.CartItemResponse,
             status_code=status.HTTP_201_CREATED)
async def create_cart_item(
    cart_item: schemas.CartItemCreate,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    customer_id_exist = await db.scalar(select(models.Customers).where(models.Customers.id == cart_item.customer_id))
    menu_item_id_exist = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == cart_item.menu_item_id,
                                                                        models.MenuItems.deleted_at.is_(None)))

    if not customer_id_exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no customer with id of {cart_item.customer_id}")
    
    if not menu_item_id_exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no menu item with id of {cart_item.menu_item_id}")

    new_cart_item = models.CartItems(**cart_item.model_dump())
    new_cart_item.store_id = customer_id_exist.store_id

    db.add(new_cart_item)

    try:
        await db.commit()
        await db.refresh(new_cart_item)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create cart item")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return new_cart_item


#stand for quick add!
@router.post("/qadd")
async def quick_add_cart_item(
    add_item: schemas.CartItemQuickUpdate,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    cart_item_exist = await db.scalar(select(models.CartItems).where(
        models.CartItems.menu_item_id == add_item.menu_item_id,
        models.CartItems.customer_id == add_item.customer_id
    ))

    if cart_item_exist:
        if cart_item_exist.quantity is None:
            cart_item_exist.quantity = 1
        else:
            cart_item_exist.quantity += 1

        try:
            await db.commit()

        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not add item to cart")

        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

        return Response(status_code=status.HTTP_200_OK, content="Successfully add item to cart")

    else:
        customer = await db.scalar(select(models.Customers).where(models.Customers.id == add_item.customer_id))
        new_cart_item = models.CartItems(
            **add_item.model_dump(),
            quantity=1
        )
        if customer:
            new_cart_item.store_id = customer.store_id

        db.add(new_cart_item)

        try:
            await db.commit()

        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create item to cart")
        
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Erro with {e}")
        
        return Response(status_code=status.HTTP_200_OK, content="Successfully create item to cart")


#stands for quick minus
@router.post("/qminus")
async def quick_minus_cart_item(
    minus_item: schemas.CartItemQuickUpdate,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    cart_item_exist = await db.scalar(select(models.CartItems).where(
        models.CartItems.customer_id == minus_item.customer_id,
        models.CartItems.menu_item_id == minus_item.menu_item_id
    ))

    if cart_item_exist:
        if cart_item_exist.quantity is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Row existed but there is no item to be minus in quantity")
        else:
            current_quantity = cart_item_exist.quantity - 1
            if current_quantity <= 0:
                try:
                    await db.delete(cart_item_exist)
                    await db.commit()

                except IntegrityError:
                    await db.rollback()
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete cart item")
            
                except Exception as e:
                    await db.rollback()
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
            
                return Response(status_code=status.HTTP_204_NO_CONTENT, content="Successfully deleted cart item")
            else:
                cart_item_exist.quantity = current_quantity
                try:
                    await db.commit()

                except IntegrityError:
                    await db.rollback()
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not minus cart item in quantity")

                except Exception as e:
                    await db.rollback()
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
                
                return Response(status_code=status.HTTP_200_OK, content="Successfully minus cart item in quantity")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is no item to be minus in quantity")


@router.get("/get_customer/{customer_id}")
async def get_cart_item_by_customer_id(
    customer_id: int,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    query_result = await db.scalars(select(models.CartItems).where(
        models.CartItems.customer_id == customer_id
    ))
    query_cart_items = query_result.all()

    enriched = []
    for cart_item in query_cart_items:
        menu = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == cart_item.menu_item_id))
        enriched.append({
            "id": cart_item.id,
            "menu_item_id": cart_item.menu_item_id,
            "customer_id": cart_item.customer_id,
            "quantity": cart_item.quantity,
            "note": cart_item.notes or "",
            "addons": cart_item.add_ons or {},
            "name": menu.name if menu else "",
            "price": float(menu.price) if menu else 0,
            "image": menu.image_url if menu else "",
        })

    return enriched


@router.get("/all",
            response_model=List[schemas.CartItemResponse])
async def get_all_cart_item(
    db: DBSession,
    payload: dict = Depends(require_staff_read_only)
):
    store_id = payload.get("store_id")

    query_result = await db.scalars(select(models.CartItems).where(
        models.CartItems.store_id == store_id
    ))
    query_cart_items = query_result.all()

    return query_cart_items


@router.get("/{cart_item_id}",
            response_model=schemas.CartItemResponse)
async def get_cart_item_by_id(
    cart_item_id: int,
    db: DBSession,
    payload: dict = Depends(get_jwt_payload)
):
    store_id = payload.get("store_id")
    query_cart_item = await db.scalar(select(models.CartItems).where(
        models.CartItems.id == cart_item_id,
        models.CartItems.store_id == store_id
    ))

    if not query_cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no cart item with id of {cart_item_id}")

    return query_cart_item


@router.patch("/{cart_item_id}",
              response_model=schemas.CartItemResponse)
async def update_cart_item_by_id(
    cart_item_id: int,
    update_data: schemas.CartItemUpdate,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    query_cart_item = await db.scalar(select(models.CartItems).where(models.CartItems.id == cart_item_id))

    if not query_cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no cart item with id of {cart_item_id}")
    
    if update_data.customer_id is not None:
        customer_id_exist = await db.scalar(select(models.Customers).where(models.Customers.id == update_data.customer_id))
        if not customer_id_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no customer with id of {update_data.customer_id}")
        
    if update_data.menu_item_id is not None:
        menu_item_id_exist = await db.scalar(select(models.MenuItems).where(models.MenuItems.id == update_data.menu_item_id))
        if not menu_item_id_exist:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"There is no menu item with id of {update_data.menu_item_id}")

    update_cart_item_dict = update_data.model_dump(exclude_unset=True)

    if not update_cart_item_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is nothing to update")

    for key, value in update_cart_item_dict.items():
        setattr(query_cart_item, key, value)

    try:
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update cart item")
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")
    
    return query_cart_item

@router.delete("/{cart_item_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_cart_item_by_id(
    cart_item_id: int,
    db: DBSession,
    payload: dict = Depends(require_customer_read_only)
):
    query_cart_item = await db.scalar(select(models.CartItems).where(models.CartItems.id == cart_item_id))

    if not query_cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"There is no cart item with id {cart_item_id}")
    
    try:
        await db.delete(query_cart_item)
        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete cart item")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal Server Error with {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT, content=f"Cart item with id of {cart_item_id} is deleted")