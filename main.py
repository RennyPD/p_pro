from fastapi import FastAPI
from app.db.database import engine, Base

from app.models import *

Base.metadata.create_all(bind=engine)

app = FastAPI()