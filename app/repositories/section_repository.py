from sqlalchemy.orm import Session
from app.models.section_model import Section
from app.schemas.section_schema import SectionCreate, SectionUpdate

def create_section(db:Session, section_data: SectionCreate):

    data = section_data.model_dump()

    if isinstance(data.get("days_of_week"), list):
      data["days_of_week"] = ", ".join([d.value for d in data["days_of_week"]])

    section = Section(**data)
    db.add(section)
    db.commit()
    db.refresh(section)
    return section

def get_sections(db:Session):
   return db.query(Section).all()

def get_section_by_id(db:Session,section_id: int):
   return db.query(Section).filter(Section.section_id == section_id).first()

def update_section(db:Session, section_id: int, section_data:SectionUpdate):
   
   section = get_section_by_id(db, section_id)

   if not section:
    return None
   
   update_data = section_data.model_dump(
    exclude_unset= True
    )
    

   for key, value in update_data.items():
    if key == "days_of_week" and isinstance(value, list):
       value = ", ".join([d.value for d in value])
    setattr(section,key, value)

   db.commit()
   db.refresh(section)

      
   return section
   
def delete_section(db:Session, section_id:int):

    section = get_section_by_id(db, section_id)

    if not section:
       return None
    
    db.delete(section)
    db.commit()

    return True