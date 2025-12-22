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

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    import traceback
    with open("debug_error.log", "a") as f:
        f.write(f"CRITICAL: Global exception handler caught: {exc}\n")
        traceback.print_exc(file=f)
    return JSONResponse(
        status_code=500,
        content={"message": f"Global Error: {exc}"},
    )

@app.on_event("startup")
async def startup_event():
    # setup_logging(app)
    with open("debug_startup.log", "w") as f:
        f.write("Startup routes:\n")
        for route in app.routes:
            methods = getattr(route, "methods", None)
            f.write(f"ROUTE: {route.path} {methods}\n")
            print(f"ROUTE: {route.path} {methods}")

@app.get("/")
def read_root():
    return {"status": "ok", "service": "AI Agent Service"}

@app.get("/debug-routes")
def get_routes():
    routes = []
    for route in app.routes:
        routes.append(f"{route.path} {getattr(route, 'methods', None)}")
    return {"routes": routes}

from fastapi.staticfiles import StaticFiles
from app.api.v1 import ai, actions, health, clients, products, uploads

# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
app.include_router(actions.router, prefix="/ai/actions", tags=["actions"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])
app.include_router(products.router, prefix="/api/v1", tags=["products"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["uploads"])
