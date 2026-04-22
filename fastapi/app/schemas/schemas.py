from __future__ import annotations

from app.models.database_models import StaffRole, TableStatus, OrderStatus, KitchenStatus

from decimal import Decimal
from typing import List
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RestaurantSettingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    open_time: str | None = Field(default=None, max_length=10)
    close_time: str | None = Field(default=None, max_length=10)
    service_charge_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    tax_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    currency_symbol: str | None = Field(default=None, max_length=5)
    background_image_url: str | None = Field(default=None, max_length=500)


class RestaurantSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    open_time: str | None = None
    close_time: str | None = None
    service_charge_pct: Decimal | None = None
    tax_pct: Decimal | None = None
    currency_symbol: str | None = None
    background_image_url: str | None = None


class RestaurantSettingUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    open_time: str | None = Field(default=None, max_length=10)
    close_time: str | None = Field(default=None, max_length=10)
    service_charge_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    tax_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    currency_symbol: str | None = Field(default=None, max_length=5)
    background_image_url: str | None = Field(default=None, max_length=500)


class StaffCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(..., min_length=8)
    display_name: str = Field(min_length=1, max_length=100)
    role: StaffRole
    is_active: bool | None = True


class StaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: str
    display_name: str
    role: StaffRole
    is_active: bool | None


class StaffUpdate(BaseModel):
    username: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=8)
    display_name: str | None = Field(default=None, max_length=100)
    role: StaffRole | None = None
    is_active: bool | None = None


class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(..., max_digits=10, decimal_places=2)
    category_id: int | None = Field(default=None, gt=0)
    image_url: str | None = Field(default=None, max_length=500)
    available: bool | None = True
    add_ons: dict[str, str] | None = Field(default_factory=dict)
    stock_enabled: bool | None = None
    stock_quantity: int | None = Field(default=None, gt=0)
    sort_order: int | None = None

    @model_validator(mode="after")
    def stock_logic(self) -> "MenuItemCreate":
        if self.stock_enabled is True:
            if self.stock_quantity is None:
                raise ValueError("need a stock_quantity when stock_enable is true")
            elif self.stock_quantity < 0:
                raise ValueError("stock_quantity cannot be negative")
            
        else:
            self.stock_quantity = None

        return self


class MenuItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    price: Decimal
    category_id: int | None = None
    image_url: str | None = None
    available: bool | None = None
    is_recommended: bool | None = None
    add_ons: dict[str, str] | None = None
    disabled_add_ons: dict[str, str] | None = None
    stock_enabled: bool | None = None
    stock_quantity: int | None = None
    sort_order: int | None = None


class MenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=0, max_digits=10, decimal_places=2)
    category_id: int | None = Field(default=None, gt=0)
    image_url: str | None = Field(default=None, max_length=500)
    available: bool | None = True
    is_recommended: bool | None = None
    add_ons: dict[str, str] | None = Field(default_factory=dict)
    stock_enabled: bool | None = None
    stock_quantity: int | None = Field(default=None, gt=0)
    sort_order: int | None = None

    @model_validator(mode="after")
    def stock_logic(self) -> "MenuItemCreate":
        if self.stock_enabled is True:
            if self.stock_quantity is None:
                raise ValueError("need a stock_quantity when stock_enable is true")
            elif self.stock_quantity < 0:
                raise ValueError("stock_quantity cannot be negative")
            
        else:
            self.stock_quantity = None

        return self


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, gt=0)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    sort_order: int | None = Field(default=None, gt=0)


class CartItemCreate(BaseModel):
    customer_id: int = Field(gt=0)
    menu_item_id: int = Field(gt=0)
    quantity: int | None = Field(default=None, gt=0)
    add_ons: dict[str, str] | None = Field(default_factory=dict)
    notes: str | None = None


class CartItemQuickUpdate(BaseModel):
    customer_id: int = Field(gt=0)
    menu_item_id: int = Field(gt=0)


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    menu_item_id: int
    quantity: int | None
    add_ons: dict[str, str] | None = None
    notes: str | None = None


class CartItemUpdate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    menu_item_id: int | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, gt=0)
    add_ons: dict[str, str] | None = Field(default_factory=dict)
    notes: str | None = None


class CustomerCreate(BaseModel):
    table_id: int = Field(gt=0)
    session_token: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    token: str = Field(min_length=1, max_length=64)
    is_active: bool | None = True


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    table_id: int
    session_token: str
    name: str
    token: str
    is_active: bool | None
    updated_at: datetime | None


class CustomerUpdate(BaseModel):
    table_id: int | None = Field(default=None, gt=0)
    session_token: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=100)
    token: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class TableCreate(BaseModel):
    number: int = Field(gt=0)
    status: TableStatus | None = TableStatus.FREE
    session_token: str | None = Field(default=None, max_length=64)
    session_started_at: datetime | None = None
    number_of_seats: int = Field(gt=0)
    location: str | None = Field(default=None, max_length=100)


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    status: TableStatus | None
    session_token: str | None
    session_started_at: datetime | None
    qr_token: str
    updated_at: datetime | None
    number_of_seats: int
    location: str | None


class TableUpdate(BaseModel):
    number: int | None = Field(default=None, gt=0)
    status: TableStatus | None = None
    session_token: str | None = Field(default=None, max_length=64)
    session_started_at: datetime | None = None
    number_of_seats: int | None = Field(default=None, gt=0)
    location: str | None = Field(default=None, max_length=100)


class OrderCreate(BaseModel):
    table_id: int | None = Field(default=None, gt=0)
    session_token: str = Field(min_length=1, max_length=64)
    customer_id: int | None = Field(default=None, gt=0)
    customer_name: str | None = Field(default=None, max_length=100)
    status: OrderStatus | None = OrderStatus.PENDING
    is_paid: bool | None = False


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    table_id: int | None
    session_token: str
    customer_id: int | None
    customer_name: str | None
    status: OrderStatus | None
    created_at: datetime | None
    updated_at: datetime | None
    is_paid: bool | None
    order_number: int | None = None


class OrderResponseWithOrderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    table_id: int | None
    session_token: str
    customer_id: int | None
    customer_name: str | None
    status: OrderStatus | None
    created_at: datetime | None
    updated_at: datetime | None
    is_paid: bool | None
    order_number: int | None = None

    order_items: List[OrderItemResponseNoOrderID] | None


class OrderUpdate(BaseModel):
    table_id: int | None = Field(default=None, gt=0)
    session_token: str | None = Field(default=None, max_length=64)
    customer_id: int | None = Field(default=None, gt=0)
    customer_name: str | None = Field(default=None, max_length=100)
    status: OrderStatus | None = None
    is_paid: bool | None = None


class OrderItemCreate(BaseModel):
    order_id: int = Field(gt=0)
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0)
    unit_price: Decimal = Field(..., max_digits=10, decimal_places=2)
    add_ons: dict[str, str] | None = Field(default_factory=dict)
    notes: str | None = None
    kitchen_status: KitchenStatus | None = None


class OrderItemResponseNoOrderID(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    name: str
    quantity: int | None
    unit_price: Decimal
    add_ons: dict[str, str] | None
    notes: str | None 
    kitchen_status: KitchenStatus | None
    created_at: datetime | None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    menu_item_id: int
    name: str
    quantity: int | None
    unit_price: Decimal
    add_ons: dict[str, str] | None
    notes: str | None
    kitchen_status: KitchenStatus | None
    created_at: datetime | None


class OrderItemUpdate(BaseModel):
    order_id: int | None = Field(default=None, gt=0)
    menu_item_id: int | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    add_ons: dict[str, str] | None = Field(default_factory=dict)
    notes: str | None = None
    kitchen_status: KitchenStatus | None = None


class DailyItemPerformanceMake(BaseModel):
    menu_item_id: int = Field(..., gt=0)
    quantity_sold: int = Field(..., gt=0)


class DailyItemPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date | None
    quantity_sold: int | None
    gross_revenue: Decimal | None

    menu_item: MenuItemResponse | None


class DailyBusinessStatsMake(BaseModel):
    total_revenue: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    total_orders: int | None = None
    completed_orders: int | None = None
    cancelled_orders: int | None = None
    total_customers: int | None = None


class DailyBusinessStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    total_revenue: Decimal | None
    total_orders: int | None
    completed_orders: int | None
    cancelled_orders: int | None
    total_customers: int | None
    average_order_value: Decimal | None