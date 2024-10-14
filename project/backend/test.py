from alembic.config import Config
from sqlalchemy import create_engine

# Load Alembic config
alembic_cfg = Config("alembic.ini")
db_url = alembic_cfg.get_main_option("sqlalchemy.url")

# Create SQLAlchemy engine
engine = create_engine(db_url)

# Test connection
try:
    with engine.connect() as connection:
        print("Successfully connected to the database:", connection.engine.url)
except Exception as e:
    print("Failed to connect to the database:", e)
