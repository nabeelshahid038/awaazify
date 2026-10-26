from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.api.v1.health import router as health_router
from app.api.v1.me import router as me_router
from app.api.v1.studio import router as studio_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.library import router as library_router
from app.api.v1.payments import router as payments_router
from app.api.v1.training import router as training_router
from app.api.v1.ops import router as ops_router
from app.api.v1.account import router as account_router
from app.api.v1.support import router as support_router
from app.core.config import settings
from app.core.middleware import ProductionHeadersMiddleware

app = FastAPI(title="Awaazify API", version="0.11.0", docs_url="/docs" if settings.environment != "production" else None, redoc_url=None)
origins = {settings.frontend_origin}
if settings.environment != "production": origins.update({"http://127.0.0.1:5173", "http://localhost:5173"})
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[item.strip() for item in settings.allowed_hosts.split(",") if item.strip()])
app.add_middleware(ProductionHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=list(origins), allow_credentials=False, allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"], expose_headers=["X-Request-ID"])
app.include_router(health_router, prefix="/api/v1")
app.include_router(me_router, prefix="/api/v1")
app.include_router(studio_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(library_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(training_router, prefix="/api/v1")
app.include_router(ops_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")
