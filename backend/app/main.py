from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import models, scan, files, collections, scrape, enrich

Base.metadata.create_all(bind=engine)

app = FastAPI(title="STL Inventory", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80", "http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models.router)
app.include_router(scan.router)
app.include_router(files.router)
app.include_router(collections.router)
app.include_router(scrape.router)
app.include_router(enrich.router)


@app.get("/health")
def health():
    return {"status": "ok"}
