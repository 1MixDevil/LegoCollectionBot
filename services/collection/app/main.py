import logging

from fastapi import FastAPI

from app.routers import figure_router, health_router, wishlist_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

app = FastAPI(title="Lego Collection — Collection Service")
app.include_router(health_router.router)
app.include_router(figure_router.router)
app.include_router(wishlist_router.router)