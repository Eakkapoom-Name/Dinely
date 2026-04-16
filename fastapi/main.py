import sys
import os
from dotenv import load_dotenv

# Add the api directory to the path for Vercel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import fastapi_app
from app.routers import (menu_items, categories, restaurant_setting,
                         staff, cart_items, customers, tables,
                         orders, order_items, daily_item_performance,
                         daily_business_stats, debug)

load_dotenv()

app = fastapi_app

# the order will be the same order as Swagger UI
app.include_router(restaurant_setting.router)
app.include_router(menu_items.router)
app.include_router(categories.router)
app.include_router(staff.router)
app.include_router(cart_items.router)
app.include_router(customers.router)
app.include_router(tables.router)
app.include_router(orders.router)
app.include_router(order_items.router)
app.include_router(daily_item_performance.router)
app.include_router(daily_business_stats.router)
app.include_router(debug.router)