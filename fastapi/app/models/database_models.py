from __future__ import annotations

from sqlalchemy import (
        Integer, String, Numeric, Text,
        ForeignKey, DateTime, Enum, Boolean, Date
    )
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from typing import List
from decimal import Decimal
from datetime import datetime, date
import enum

from app.db import Base

# use attr index=True when that column is used for search


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class RestaurantSettings(Base):
    __tablename__ = "restaurant_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    open_time: Mapped[str | None] = mapped_column(String(10))
    close_time: Mapped[str | None] = mapped_column(String(10))
    service_charge_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tax_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    currency_symbol: Mapped[str | None] = mapped_column(String(5))
    background_image_url: Mapped[str | None] = mapped_column(String(500))


class StaffRole(enum.Enum):
    ADMIN = "admin"
    KITCHEN = "kitchen"
    CASHIER = "cashier"


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    username: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole,
                                                 native_enum=False,
                                                 values_callable=lambda enum_status: [e.value for e in enum_status]))
    is_active: Mapped[bool | None] = mapped_column(Boolean)


class Categories(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # -- Relationship(s) ---
    menu_items: Mapped[List[MenuItems]] = relationship(back_populates="category")


class MenuItems(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # link with categories id
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    image_url: Mapped[str | None] = mapped_column(String(500))
    available: Mapped[bool | None] = mapped_column(Boolean)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    add_ons: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    disabled_add_ons: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    stock_enabled: Mapped[bool | None] = mapped_column(Boolean)
    stock_quantity: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Relationship(s) ---
    category: Mapped[Categories] = relationship(back_populates="menu_items")
    cart_items: Mapped[List[CartItems]] = relationship(back_populates="menu_item")
    order_items: Mapped[List[OrderItems]] = relationship(back_populates="menu_item")


class CartItems(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    # link with customers id
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    # link with menu_items id
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    quantity: Mapped[int | None] = mapped_column(Integer)
    add_ons: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    # --- Relationship(s) ---
    customer: Mapped[Customers] = relationship(back_populates="cart_items")
    menu_item: Mapped[MenuItems] = relationship(back_populates="cart_items")


class Customers(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    # link with table id
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id"))
    session_token: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    token: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Relationship(s) ---
    cart_items: Mapped[List[CartItems]] = relationship(back_populates="customer")
    order: Mapped[Orders] = relationship(back_populates="customer")


class TableStatus(enum.Enum):
    FREE = "free"
    OCCUPIED = "occupied"  # kept for backward compat
    PENDING = "pending"
    PREPARING = "preparing"
    WAITING_FOR_PAYMENT = "waiting_for_payment"


class Tables(Base):
    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[TableStatus | None] = mapped_column(Enum(TableStatus,
                                                            native_enum=False,
                                                            values_callable=lambda enum_status: [e.value for e in enum_status]))
    session_token: Mapped[str | None] = mapped_column(String(64))
    session_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qr_token: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    number_of_seats: Mapped[int] = mapped_column(Integer, default=4)
    location: Mapped[str | None] = mapped_column(String(100))


class OrderStatus(enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class Orders(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    # link with table id
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id"))
    session_token: Mapped[str] = mapped_column(String(64))
    # link with customer id
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    customer_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[OrderStatus | None] = mapped_column(Enum(OrderStatus,
                                                            native_enum=False,
                                                            values_callable=lambda enum_status: [e.value for e in enum_status]))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_paid: Mapped[bool | None] = mapped_column(Boolean)
    order_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Relationship(s) ---
    customer: Mapped[Customers] = relationship(back_populates="order")
    order_items: Mapped[List[OrderItems]] = relationship(back_populates="order")


class KitchenStatus(enum.Enum):
    PENDING = "pending"  # backward compat
    PREPARING = "preparing"
    READY = "ready"  # backward compat
    SERVED = "served"  # backward compat
    FINISHED = "finished"
    CANCELLED = "cancelled"


class OrderItems(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    # link with orders id
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    # link with menu_items id
    menu_item_id: Mapped[int | None] = mapped_column(ForeignKey("menu_items.id"))
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int | None] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    add_ons: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    kitchen_status: Mapped[KitchenStatus | None] = mapped_column(Enum(KitchenStatus,
                                                                      native_enum=False,
                                                                      values_callable=lambda enum_status: [e.value for e in enum_status]),
                                                                      default=KitchenStatus.PENDING)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Relationship(s) ---
    order: Mapped[Orders] = relationship(back_populates="order_items")
    menu_item: Mapped[MenuItems] = relationship(back_populates="order_items")


class DailyItemPerformance(Base):
    __tablename__ = "daily_item_performance"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    # link with menu_item id
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), primary_key=True)
    quantity_sold: Mapped[int | None] = mapped_column(Integer)
    gross_revenue: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # --- Relationship(s) ---
    menu_item: Mapped[MenuItems] = relationship()


class DailyBusinessStats(Base):
    __tablename__ = "daily_business_stats"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    total_revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_orders: Mapped[int | None] = mapped_column(Integer)
    completed_orders: Mapped[int | None] = mapped_column(Integer)
    cancelled_orders: Mapped[int | None] = mapped_column(Integer)
    total_customers: Mapped[int | None] = mapped_column(Integer)
    average_order_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
