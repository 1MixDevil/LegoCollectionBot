from fastapi import FastAPI

from app.routers import debug_router, health_router, permissions_router, user_router

app = FastAPI(title="Lego Collection — Auth Service")

app.include_router(health_router.router)
app.include_router(user_router.router)
app.include_router(permissions_router.router)
app.include_router(debug_router.router)
