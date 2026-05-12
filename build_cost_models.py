from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Structure(Base):
    __tablename__ = "structures"
    system: Mapped[str | None] = mapped_column(String, nullable=True)
    structure: Mapped[str | None] = mapped_column(String, nullable=True)
    system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structure_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rig_1: Mapped[str | None] = mapped_column(String, nullable=True)
    rig_2: Mapped[str | None] = mapped_column(String, nullable=True)
    rig_3: Mapped[str | None] = mapped_column(String, nullable=True)
    structure_type: Mapped[str | None] = mapped_column(String, nullable=True)
    structure_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax: Mapped[float | None] = mapped_column(Float, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    region_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Structure(system={self.system}, structure={self.structure}, "
            f"system_id={self.system_id}, structure_id={self.structure_id}, "
            f"rig_1={self.rig_1}, rig_2={self.rig_2}, rig_3={self.rig_3}, "
            f"structure_type={self.structure_type}, "
            f"structure_type_id={self.structure_type_id}, tax={self.tax}, "
            f"region={self.region}, region_id={self.region_id})>"
        )


class IndustryIndex(Base):
    __tablename__ = "industry_index"
    solar_system_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manufacturing: Mapped[float] = mapped_column(Float)
    researching_time_efficiency: Mapped[float] = mapped_column(Float)
    researching_material_efficiency: Mapped[float] = mapped_column(Float)
    copying: Mapped[float] = mapped_column(Float)
    invention: Mapped[float] = mapped_column(Float)
    reaction: Mapped[float] = mapped_column(Float)

    def __repr__(self) -> str:
        return (
            f"<IndustryIndex(solar_system_id={self.solar_system_id}, "
            f"manufacturing={self.manufacturing}, "
            f"researching_time_efficiency={self.researching_time_efficiency}, "
            f"researching_material_efficiency={self.researching_material_efficiency}, "
            f"copying={self.copying}, invention={self.invention}, "
            f"reaction={self.reaction})>"
        )


class Rig(Base):
    __tablename__ = "rigs"
    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_name: Mapped[str] = mapped_column(String)
    icon_id: Mapped[int] = mapped_column(Integer)

    def __repr__(self) -> str:
        return (
            f"<Rig(type_id={self.type_id}, type_name={self.type_name}, "
            f"icon_id={self.icon_id})>"
        )


class UpdateLog(Base):
    __tablename__ = "updatelog"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"<UpdateLog(id={self.id!r}, table_name={self.table_name!r}, "
            f"timestamp={self.timestamp!r})>"
        )


if __name__ == "__main__":
    pass
