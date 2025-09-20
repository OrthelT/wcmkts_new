from sqlalchemy import create_engine, text
import streamlit as st
import libsql
from logging_config import setup_logging
import sqlite3 as sql
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import UpdateLog


logger = setup_logging(__name__)

class DatabaseConfig:

    wcdbmap = "wcmkt2" #master config variable for the database to use

    _db_paths = {
        "wcmkt2": "wcmkt2.db", #production database
        "sde": "sde.db",
        "build_cost": "buildcost.db",
    }

    _db_turso_urls = {
        "wcmkt2_turso": st.secrets.wcmkt2_turso.url,
        "sde_turso": st.secrets.sde_aws_turso.url,
        "build_cost_turso": st.secrets.buildcost_turso.url,
    }

    _db_turso_auth_tokens = {
        "wcmkt2_turso": st.secrets.wcmkt2_turso.token,
        "sde_turso": st.secrets.sde_aws_turso.token,
        "build_cost_turso": st.secrets.buildcost_turso.token,
    }

    def __init__(self, alias: str, dialect: str = "sqlite+libsql"):
        if alias == "wcmkt":
            alias = self.wcdbmap
        elif alias == "wcmkt2" or alias == "wcmkt3":
            logger.warning(f"Alias {alias} is deprecated, using {self.wcdbmap} instead")
            alias = self.wcdbmap

        if alias not in self._db_paths:
            raise ValueError(f"Unknown database alias '{alias}'. "
                             f"Available: {list(self._db_paths.keys())}")
        self.alias = alias
        self.path = self._db_paths[alias]
        self.url = f"{dialect}:///{self.path}"
        self.turso_url = self._db_turso_urls[f"{self.alias}_turso"]
        self.token = self._db_turso_auth_tokens[f"{self.alias}_turso"]
        self._engine = None
        self._remote_engine = None
        self._libsql_connect = None
        self._libsql_sync_connect = None
        self._sqlite_local_connect = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(self.url)
        return self._engine

    @property
    def remote_engine(self):
        if self._remote_engine is None:
            turso_url = self._db_turso_urls[f"{self.alias}_turso"]
            auth_token = self._db_turso_auth_tokens[f"{self.alias}_turso"]
            self._remote_engine = create_engine(f"sqlite+{turso_url}?secure=true", connect_args={"auth_token": auth_token,},)
        return self._remote_engine

    @property
    def libsql_local_connect(self):
        if self._libsql_connect is None:
            self._libsql_connect = libsql.connect(self.path)
        return self._libsql_connect

    @property
    def libsql_sync_connect(self):
        if self._libsql_sync_connect is None:
            self._libsql_sync_connect = libsql.connect(self.path, sync_url = self.turso_url, auth_token=self.token)
        return self._libsql_sync_connect

    @property
    def sqlite_local_connect(self):
        if self._sqlite_local_connect is None:
            self._sqlite_local_connect = sql.connect(self.path)
        return self._sqlite_local_connect

    def sync(self):
        with self.libsql_sync_connect as conn:
            logger.info("Syncing database...")
            conn.sync()
        conn.close()
        update_time = datetime.now(timezone.utc)
        logger.info(f"Database synced at {update_time} UTC")

        if self.alias == "wcmkt2":
            validation_test = self.validate_sync()
            st.session_state.sync_status = "Success" if validation_test else "Failed"
        st.session_state.sync_check = False

    def validate_sync(self)-> bool:
        alias = self.alias
        with self.remote_engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(last_update) FROM marketstats")).fetchone()
            remote_last_update = result[0]
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(last_update) FROM marketstats")).fetchone()
            local_last_update = result[0]
        logger.info(f"remote_last_update: {remote_last_update}")
        logger.info(f"local_last_update: {local_last_update}")
        validation_test = remote_last_update == local_last_update
        logger.info(f"validation_test: {validation_test}")
        return validation_test

    def get_table_list(self, local_only: bool = True)-> list[tuple]:
        if local_only:
            engine = self.engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [table.name for table in tables if "sqlite" not in table.name]
                return table_list
        else:
            engine = self.remote_engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [table.name for table in tables if "sqlite" not in table.name]
                return table_list

    def get_table_columns(self, table_name: str, local_only: bool = True, full_info: bool = False) -> list[dict]:
        """
        Get column information for a specific table.

        Args:
            table_name: Name of the table to inspect
            local_only: If True, use local database; if False, use remote database

        Returns:
            List of dictionaries containing column information
        """
        if local_only:
            engine = self.engine
        else:
            engine = self.remote_engine

        with engine.connect() as conn:
            # Use string formatting for PRAGMA since it doesn't support parameterized queries well
            stmt = text(f"PRAGMA table_info({table_name})")
            result = conn.execute(stmt)
            columns = result.fetchall()
            if full_info:
                column_info = []
                for col in columns:
                    column_info.append({
                    "cid": col.cid,
                    "name": col.name,
                    "type": col.type,
                    "notnull": col.notnull,
                    "dflt_value": col.dflt_value,
                    "pk": col.pk
                })
            else:
                column_info = [col.name for col in columns]
            return column_info

    def get_most_recent_update(self, table_name: str, remote: bool = False)-> datetime:
        """
        Get the most recent update time for a specific table
        Args:
            table_name: str - The name of the table to get the most recent update time for
            remote: bool - If True, get the most recent update time from the remote database, if False, get the most recent update time from the local database

        Returns:
            The most recent update time for the table
        """
        engine = self.remote_engine if remote else self.engine
        session = Session(bind=engine)
        with session.begin():
            updates = select(UpdateLog.timestamp).where(UpdateLog.table_name == table_name).order_by(UpdateLog.timestamp.desc())
            result = session.execute(updates).fetchone()
        session.close()
        update_time = result[0] if result is not None else None
        update_time = update_time.replace(tzinfo=timezone.utc) if update_time is not None else None
        print(f"update_time: {update_time}")
        return update_time

    def get_time_since_update(self, table_name: str = "marketstats", remote: bool = False):
        status = self.get_most_recent_update(table_name, remote=remote)
        logger.info(f"status: {status}")
        return status[0] if status is not None else None

def fill_type_name(type_id: int) -> str:
    sde_db = DatabaseConfig("sde")
    engine = sde_db.engine
    with engine.connect() as conn:
        stmt = text("SELECT typeName FROM inv_info WHERE typeID = :type_id")
        res = conn.execute(stmt, {"type_id": type_id})
        type_name = res.fetchone()[0] if res.fetchone() is not None else None
    conn.close()
    return type_name

if __name__ == "__main__":
    pass
