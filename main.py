import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.database import settings
from app.logging_config import configure_logging
from app.models import *
from app.routers.academic_router import router as academic_router
from app.routers.access_router import router as access_router
from app.routers.assessment_router import router as assessment_router
from app.routers.attendance_router import router as attendance_router
from app.routers.audit_router import router as audit_router
from app.routers.auth_router import router as auth_router
from app.routers.bulk_router import router as bulk_router
from app.routers.career_router import router as career_router
from app.routers.class_group_router import router as class_group_router
from app.routers.community_router import router as community_router
from app.routers.configuration_router import router as configuration_router
from app.routers.curriculum_router import router as curriculum_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.document_router import router as document_router
from app.routers.enrollment_router import router as enrollment_router
from app.routers.finance_router import router as finance_router
from app.routers.governance_router import router as governance_router
from app.routers.grade_router import router as grade_router
from app.routers.guardian_router import router as guardian_router
from app.routers.module_router import router as module_router
from app.routers.operations_router import router as operations_router
from app.routers.record_router import router as record_router
from app.routers.role_router import router as role_router
from app.routers.scheduling_router import router as scheduling_router
from app.routers.school_year_router import router as school_year_router
from app.routers.section_router import router as section_router
from app.routers.student_router import router as student_router
from app.routers.subject_router import router as subject_router
from app.routers.teacher_router import router as teacher_router
from app.routers.user_router import router as user_router
from app.services.validation_messages import spanish_message

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Has-More"],
)


@app.get("/health", tags=["system"])
def health():
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}


configure_logging()
logger = logging.getLogger("nexo.api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response


def _request_fields(request: Request) -> dict:
    return {
        "request_id": getattr(request.state, "request_id", None),
        "method": request.method,
        "path": request.url.path,
    }


@app.exception_handler(IntegrityError)
def handle_integrity_error(request, exc):
    logger.warning("integrity_error", extra={**_request_fields(request), "error": str(exc.orig)})
    return JSONResponse(
        status_code=409, content={"detail": "La operación entra en conflicto con datos existentes"}
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(_request, exc):
    # Pydantic's input and context may contain the entire submitted form.
    errors = [
        {"loc": error["loc"], "type": error["type"], "msg": spanish_message(error)}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(SQLAlchemyError)
def handle_database_error(request, exc):
    logger.error("database_error", extra=_request_fields(request), exc_info=exc)
    return JSONResponse(
        status_code=500, content={"detail": "No se pudo completar la operación en la base de datos"}
    )


app.include_router(auth_router)
app.include_router(access_router)
app.include_router(audit_router)
app.include_router(career_router)
app.include_router(configuration_router)
app.include_router(school_year_router)
app.include_router(class_group_router)
app.include_router(community_router)
app.include_router(curriculum_router)
app.include_router(dashboard_router)
app.include_router(document_router)
app.include_router(bulk_router)
app.include_router(attendance_router)
app.include_router(assessment_router)
app.include_router(academic_router)
app.include_router(student_router)
app.include_router(teacher_router)
app.include_router(section_router)
app.include_router(scheduling_router)
app.include_router(subject_router)
app.include_router(user_router)
app.include_router(enrollment_router)
app.include_router(role_router)
app.include_router(record_router)
app.include_router(grade_router)
app.include_router(governance_router)
app.include_router(finance_router)
app.include_router(operations_router)
app.include_router(module_router)
app.include_router(guardian_router)
