from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv() # Load .env file explicitly

from app.core.logging import setup_logging
from app.api.v1 import ai, actions, health, clients

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Agent Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    setup_logging(app)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "AI Agent Service"}

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
app.include_router(actions.router, prefix="/ai/actions", tags=["actions"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])
