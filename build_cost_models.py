from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy import text
import pandas as pd


build_cost_db = "build_cost.db"
build_cost_url = f"sqlite:///{build_cost_db}"

Base = declarative_base()

class Structure(Base):
    __tablename__ = "structures"
    system = Column(String)
    structure = Column(String)
    system_id = Column(Integer)
    structure_id = Column(Integer, primary_key=True)
    rig_1 = Column(String)
    rig_2 = Column(String)
    rig_3 = Column(String)
    structure_type = Column(String)
    structure_type_id = Column(Integer)
    tax = Column(Float)
    
    def __repr__(self):
        return f"<Structure(system={self.system}, structure={self.structure}, system_id={self.system_id}, structure_id={self.structure_id}, rig_1={self.rig_1}, rig_2={self.rig_2}, rig_3={self.rig_3}, structure_type={self.structure_type}, structure_type_id={self.structure_type_id}, tax={self.tax})>"

class IndustryIndex(Base):
    __tablename__ = "industry_index"
    solar_system_id = Column(Integer, primary_key=True)
    manufacturing = Column(Float)
    researching_time_efficiency = Column(Float)
    researching_material_efficiency = Column(Float)
    copying = Column(Float)
    invention = Column(Float)
    reaction = Column(Float)

    def __repr__(self):
        return f"<IndustryIndex(solar_system_id={self.solar_system_id}, manufacturing={self.manufacturing}, researching_time_efficiency={self.researching_time_efficiency}, researching_material_efficiency={self.researching_material_efficiency}, copying={self.copying}, invention={self.invention}, reaction={self.reaction})>"
class Rig(Base):
    __tablename__ = "rigs"
    type_id = Column(Integer, primary_key=True)
    type_name = Column(String)
    icon_id = Column(Integer)

    def __repr__(self):
        return f"<Rig(type_id={self.type_id}, type_name={self.type_name}, icon_id={self.icon_id})>"
    
if __name__ == "__main__":
    pass

