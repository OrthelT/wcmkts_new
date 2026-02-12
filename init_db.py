from config import DatabaseConfig
import os
from logging_config import setup_logging
from sync_state import update_wcmkt_state
from time import perf_counter
from init_equivalents import init_module_equivalents, get_equivalents_count
from settings_service import get_all_market_configs

logger = setup_logging(__name__)
def verify_db_path(path):
    if not os.path.exists(path):
        logger.warning(f"DB path does not exist: {path}")
        return False
    return True

def init_db():
    """ This function checks to see if the databases are available locally. If not, it will sync the databases from the remote server using the configuration in given in the config.py file, using credentials stored in the .streamlit/secrets.toml (for local development) or st.secrets (for production). This code was designed to be used with sqlite embedded-replica databases hosted on Turso Cloud.
    """
    start_time = perf_counter()
    logger.info("-"*100)
    logger.info("initializing databases")
    logger.info("-"*100)

    # Initialize ALL market databases plus shared databases
    market_configs = get_all_market_configs()
    db_paths = {}

    for key, cfg in market_configs.items():
        try:
            mkt_db = DatabaseConfig(cfg.database_alias)
            db_paths[mkt_db.alias] = mkt_db.path
        except ValueError:
            logger.warning(f"Skipping unknown market alias: {cfg.database_alias}")

    # Add shared databases
    sde_db = DatabaseConfig("sde")
    build_cost_db = DatabaseConfig("build_cost")
    db_paths[sde_db.alias] = sde_db.path
    db_paths[build_cost_db.alias] = build_cost_db.path

    status = {}

    for key, value in db_paths.items():
        alias = key
        db_path = value
        db = DatabaseConfig(alias)

        try:
            if verify_db_path(db_path):
                logger.info(f"DB path exists: {db_path}✔️")
                status = {key: "success initialized🟢" if verify_db_path(db_path) else "failed🔴"}
            else:
                logger.warning(f"DB path does not exist: {db_path}⚠️")
                logger.info("syncing db")
                logger.info(f"syncing db: {db_path}🛜")
                db.sync()
                status = {key: "initialized and synced🟢" if verify_db_path(db_path) else "failed🔴"}
        except Exception as e:
                logger.error(f"Error syncing db: {e}")
                status = {key: "failed🔴"}
        logger.info(f"db initialization status: {key}: {status[key]}")
    logger.info("-"*100)
    logger.info("updating wcmkt state")
    logger.info("-"*100)

    logger.info("wcmkt state updated✅")

    # Initialize module equivalents table for all market databases
    logger.info("-"*100)
    logger.info("initializing module equivalents")
    logger.info("-"*100)

    for key, cfg in market_configs.items():
        try:
            mkt_db = DatabaseConfig(cfg.database_alias)
            equiv_count = get_equivalents_count(mkt_db)
            if equiv_count == 0:
                init_module_equivalents(mkt_db)
                equiv_count = get_equivalents_count(mkt_db)
            logger.info(f"module equivalents count ({cfg.database_alias}): {equiv_count}")
        except Exception as e:
            logger.warning(f"Could not init equivalents for {cfg.database_alias}: {e}")

    logger.info("-"*100)

    end_time = perf_counter()
    elapsed_time = round((end_time-start_time)*1000, 2)
    logger.info(f"TIME init_db() = {elapsed_time} ms")
    logger.info("-"*100)


    return True

if __name__ == "__main__":
    pass
