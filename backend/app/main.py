from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

from app.routers import cases, demo, evals, health, interconnection, review, rules

app = FastAPI(
    title="Project Greenlight",
    summary="DER interconnection applications, reviewed by an agent, approved by a human.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(interconnection.router)
app.include_router(cases.router)
app.include_router(rules.router)
app.include_router(review.router)
app.include_router(evals.router)
app.include_router(demo.router)
