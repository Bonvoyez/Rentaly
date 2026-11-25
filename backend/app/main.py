from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.models import entities  # 6개 테이블 모델 등록용
from app.inspections import router as inspections_router
from app.routers import admin_auth, admin_inspections
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 PostgreSQL에 6개 테이블이 없으면 자동 생성
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield


app = FastAPI(title="Rentaly Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inspections_router)
app.include_router(admin_auth.router)
app.include_router(admin_inspections.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request, exc):
    err = exc.errors()[0]
    field = ".".join(str(x) for x in err["loc"][1:]) or "request"
    return JSONResponse(
        status_code=422,
        content={"status": "ERROR", "error_code": "INVALID_REQUEST", "message": f"{field}: {err['msg']}"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}