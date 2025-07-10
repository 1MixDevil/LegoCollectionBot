# app/main.py
from fastapi import FastAPI
from app.core.db import engine, Base
from app.routers import user_router, permissions_router, debug_router

app = FastAPI(title="Authorization Service")

app.include_router(user_router.router)
app.include_router(permissions_router.router)
app.include_router(debug_router.router)
