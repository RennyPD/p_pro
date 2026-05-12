from fastapi import FastAPI
from app.db.database import engine, Base
from app.routers.student_router import (router as student_router)
from app.routers.teacher_router import (router as teacher_router)
from app.routers.section_router import (router as section_router)

from app.models import *

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(student_router)
app.include_router(teacher_router)
app.include_router(section_router)