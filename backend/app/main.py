from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db import Base, engine, get_db
from app import models  # register ORM metadata
from app.routers.auth import router as auth_router
settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug)
app.include_router(auth_router)

@app.on_event("startup")
def create_dev_schema():
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"name": settings.app_name, "docs":"/docs"}

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status":"ok", "database":"ok"}
    except Exception:
        return {"status":"degraded", "database":"unavailable"}
