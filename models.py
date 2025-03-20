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

def mkt_orders_to_db(df):
    engine = create_engine(local_db)
    
    Session = sessionmaker(bind=engine)

    with Session.begin() as session:
        session.query(MarketOrder).delete()
        session.bulk_insert_mappings(MarketOrder, df.to_dict(orient="records"))
        session.commit()
        session.close()

def get_expiring_orders(df:pd.DataFrame):
    df = df[df.is_buy_order == False]
    df["issued"] = pd.to_datetime(df["issued"]).dt.date
    df['duration']=pd.to_timedelta(df["duration"], unit="days")
    df['expiry'] = df['issued'] + df['duration']
    df['days_to_expiry'] = (df['expiry'] - date.today())
    df['days_to_expiry'] = df['days_to_expiry'].apply(lambda x: x.days)


    df_agg = df.groupby(['type_id']).agg({'volume_remain': 'sum'}).reset_index()
    df_exp = df[df['days_to_expiry'] < 5]


    df_expiring = df_exp.groupby(['type_id', 'type_name']).agg({'days_to_expiry': 'min', 'volume_remain': 'sum'}).sort_values(by='days_to_expiry', ascending=False).reset_index()
    df_expiring.rename(columns={'volume_remain': 'expiring_volume'}, inplace=True)
    
    df_expiring = df_expiring.merge(df_agg, how='left', on='type_id')

    df_expiring['percentage'] = (df_expiring['expiring_volume'] / df_expiring['volume_remain']) * 100
    df_expiring['percentage'] = df_expiring['percentage'].apply(lambda x: x if x < 100 else 100)
    df_expiring['percentage'] = df_expiring['percentage'].astype(int)

    return df_expiring



if __name__ == "__main__":
    pass
