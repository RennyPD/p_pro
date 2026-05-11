from pydantic import BaseModel, EmailStr

class TeacherCreate(BaseModel):
    first_name:str
    last_name:str
    specialty:str
    email: EmailStr
    telephone: str
    address: str
    activer: bool = True

class TeacherUptade(BaseModel):
    first_name:str | None = None
    last_name:str | None = None
    specialty:str | None = None
    email: EmailStr | None = None
    telephone: str | None = None
    address: str | None = None
    activer: bool | None = None

class TeacherOut(BaseModel):
    first_name:str
    last_name:str
    specialty:str
    email: EmailStr
    telephone: str
    address: str
    activer: bool
    
    class Config:
        from_attributes = True