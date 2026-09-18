from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.database import settings
from app.models import *
from app.routers.academic_router import router as academic_router
from app.routers.assessment_router import router as assessment_router
from app.routers.attendance_router import router as attendance_router
from app.routers.audit_router import router as audit_router
from app.routers.auth_router import router as auth_router
from app.routers.bulk_router import router as bulk_router
from app.routers.career_router import router as career_router
from app.routers.configuration_router import router as configuration_router
from app.routers.curriculum_router import router as curriculum_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.enrollment_router import router as enrollment_router
from app.routers.finance_router import router as finance_router
from app.routers.grade_router import router as grade_router
from app.routers.role_router import router as role_router
from app.routers.scheduling_router import router as scheduling_router
from app.routers.section_router import router as section_router
from app.routers.student_router import router as student_router
from app.routers.subject_router import router as subject_router
from app.routers.teacher_router import router as teacher_router
from app.routers.user_router import router as user_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
def handle_integrity_error(_request, _exc):
    return JSONResponse(status_code=409, content={"detail": "Database constraint conflict"})


@app.exception_handler(SQLAlchemyError)
def handle_database_error(_request, _exc):
    return JSONResponse(status_code=500, content={"detail": "Database operation failed"})


app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(career_router)
app.include_router(configuration_router)
app.include_router(curriculum_router)
app.include_router(dashboard_router)
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
app.include_router(grade_router)
app.include_router(finance_router)
