from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from routers import auth_routes, schema_routes
from core.models import Base
from core.database import engine
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)



app = FastAPI(
    title="FlowGuard",
    description="API for FlowGuard - A flow-based security management system.",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


app.include_router(auth_routes.router, prefix="/auth")
app.include_router(schema_routes.router, prefix="/api/schemas")

@app.get("/")
async def read_root():
    return {"message": "Welcome to FlowGuard API!"}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="FlowGuard API",
        version="1.0.0",
        description="AI-Assisted API Failure Testing & Stability Scoring Platform",
        routes=app.routes,
    )

    # Add Bearer Token header
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Enter: **Bearer &lt;your_token&gt;**"
        }
    }

    # Apply BearerAuth globally to all endpoints
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method in ["get", "post", "put", "delete", "patch"]:
                openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
