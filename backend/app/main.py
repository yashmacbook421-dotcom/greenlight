from fastapi import FastAPI

from app.routers import cases, health, interconnection, rules

app = FastAPI(
    title="Project Greenlight",
    summary="DER interconnection applications, reviewed by an agent, approved by a human.",
)
app.include_router(health.router)
app.include_router(interconnection.router)
app.include_router(cases.router)
app.include_router(rules.router)
