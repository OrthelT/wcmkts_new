from sqlalchemy import Integer, String, Float, Boolean, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class InvTypes(Base):
    __tablename__ = "invTypes"
    typeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    groupID: Mapped[int] = mapped_column(Integer)
    typeName: Mapped[str] = mapped_column(String)
    mass: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    capacity: Mapped[float] = mapped_column(Float)
    portionSize: Mapped[int] = mapped_column(Integer)
    raceID: Mapped[int] = mapped_column(Integer)
    basePrice: Mapped[float] = mapped_column(Float)
    published: Mapped[bool] = mapped_column(Boolean)
    marketGroupID: Mapped[int] = mapped_column(Integer)
    iconID: Mapped[int] = mapped_column(Integer)
    soundID: Mapped[int] = mapped_column(Integer)
    graphicID: Mapped[int] = mapped_column(Integer)

    def __repr__(self) -> str:
        return f"invTypes(typeID={self.typeID!r}, groupID={self.groupID!r}, typeName={self.typeName!r}, mass={self.mass!r}, volume={self.volume!r}, capacity={self.capacity!r}, portionSize={self.portionSize!r}, raceID={self.raceID!r}, basePrice={self.basePrice!r}, published={self.published!r}, marketGroupID={self.marketGroupID!r}, iconID={self.iconID!r}, soundID={self.soundID!r}, graphicID={self.graphicID!r})"

class InvGroups(Base):
    __tablename__ = "invGroups"
    groupID: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoryID: Mapped[int] = mapped_column(Integer)
    groupName: Mapped[str] = mapped_column(String)
    iconID: Mapped[int] = mapped_column(Integer)
    useBasePrice: Mapped[bool] = mapped_column(Boolean)
    anchored: Mapped[bool] = mapped_column(Boolean)
    anchorable: Mapped[bool] = mapped_column(Boolean)
    fittableNonSingleton: Mapped[bool] = mapped_column(Boolean)
    published: Mapped[bool] = mapped_column(Boolean)

    def __repr__(self) -> str:
        return f"invGroups(groupID={self.groupID!r}, categoryID={self.categoryID!r}, groupName={self.groupName!r}, iconID={self.iconID!r}, useBasePrice={self.useBasePrice!r}, anchored={self.anchored!r}, anchorable={self.anchorable!r}, fittableNonSingleton={self.fittableNonSingleton!r}, published={self.published!r})"

class InvCategories(Base):
    __tablename__ = "invCategories"
    categoryID: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoryName: Mapped[str] = mapped_column(String)
    iconID: Mapped[int] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean)

    def __repr__(self) -> str:
        return f"invCategories(categoryID={self.categoryID!r}, categoryName={self.categoryName!r}, iconID={self.iconID!r}, published={self.published!r})"

class SdeTypes(Base):
    __tablename__ = "sdeTypes"
    typeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    typeName: Mapped[str] = mapped_column(String)
    groupID: Mapped[int] = mapped_column(Integer)
    groupName: Mapped[str] = mapped_column(String)
    categoryID: Mapped[int] = mapped_column(Integer)
    volume: Mapped[float] = mapped_column(Float)

    def __repr__(self) -> str:
        return f"sdeTypes(typeID={self.typeID!r}, typeName={self.typeName!r}, groupID={self.groupID!r}, groupName={self.groupName!r}, categoryID={self.categoryID!r}, volume={self.volume!r})"

class InvMetaTypes(Base):
    __tablename__ = "invMetaTypes"
    typeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    parentTypeID: Mapped[int] = mapped_column(Integer, nullable=True)
    metaGroupID: Mapped[int] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"invMetaTypes(typeID={self.typeID!r}, parentTypeID={self.parentTypeID!r}, metaGroupID={self.metaGroupID!r})"

class InvMetaGroups(Base):
    __tablename__ = "invMetaGroups"
    metaGroupID: Mapped[int] = mapped_column(Integer, primary_key=True)
    metaGroupName: Mapped[str] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    iconID: Mapped[int] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"invMetaGroups(metaGroupID={self.metaGroupID!r}, metaGroupName={self.metaGroupName!r}, description={self.description!r}, iconID={self.iconID!r})"

if __name__ == "__main__":
    pass