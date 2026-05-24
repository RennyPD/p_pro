from fastapi import FastAPI
from app.db.database import engine, Base
from app.routers.student_router import (router as student_router)
from app.routers.teacher_router import (router as teacher_router)
from app.routers.section_router import (router as section_router)
from app.routers.subject_router import (router as subject_router)
from app.routers.user_router import (router as user_router)
from app.routers.enrollment_router import (router as enrollment_router)
from app.routers.role_router import (router as role_router)
from app.routers.grade_router import (router as grade_router)
from app.routers.career_router import (router as career_router)
from app.routers.attendance_router import (router as attendance_router)


from app.models import *

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(student_router)
app.include_router(teacher_router)
app.include_router(section_router)
app.include_router(subject_router)
app.include_router(user_router)
app.include_router(enrollment_router)
app.include_router(role_router)
app.include_router(grade_router)
app.include_router(career_router)
app.include_router(attendance_router)