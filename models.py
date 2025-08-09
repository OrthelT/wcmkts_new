from sqlalchemy import Column, Integer, String, Date, Float, Boolean, create_engine, DateTime, text
from datetime import date, datetime, timedelta
import pandas as pd
import json

from sqlalchemy.orm import declarative_base, sessionmaker


local_db = "sqlite:///market_data.db"
market_latest = "/mnt/c/Users/User/PycharmProjects/eveESO/output/brazil/new_orders.csv"

Base = declarative_base()

class MarketOrder(Base):
    __tablename__ = 'marketOrders'
    order_id = Column(Integer, primary_key=True)
    is_buy_order = Column(Boolean)
    type_id = Column(Integer)
    duration = Column(Integer)
    issued = Column(DateTime)
    price = Column(Float)
    volume_remain = Column(Integer)

class InvType(Base):
    __tablename__ = 'invTypes'
    typeID = Column(Integer, primary_key=True)
    groupID = Column(Integer)
    typeName = Column(String)
    description = Column(String)
    mass = Column(Float)
    volume = Column(Float)
    capacity = Column(Float)
    portionSize = Column(Integer)
    raceID = Column(Integer)
    basePrice = Column(Float)
    published = Column(Boolean)
    marketGroupID = Column(Integer)
    iconID = Column(Integer)
    soundID = Column(Integer)
    graphicID = Column(Integer)


if __name__ == "__main__":
    pass