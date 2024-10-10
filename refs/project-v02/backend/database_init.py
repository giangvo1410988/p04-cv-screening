import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Import your models here
from models import Base, User, Folder, File, JobDescription

def setup_postgres():
    # Connect to PostgreSQL (default)
    conn = psycopg2.connect(dbname='postgres', user='postgres', host='localhost', password='sharecv101')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Check if database exists and drop if it does
    cur.execute("SELECT 1 FROM pg_database WHERE datname='cvscreening'")
    if cur.fetchone():
        # Revoke connections to the database
        cur.execute("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'cvscreening'
            AND pid <> pg_backend_pid();
        """)
        # Drop the database
        cur.execute("DROP DATABASE cvscreening")
        print("Existing database 'cvscreening' dropped.")

    # Check if user exists and drop if it does
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname='cvscreening_user'")
    if cur.fetchone():
        # Reassign owned objects and drop the user
        cur.execute("REASSIGN OWNED BY cvscreening_user TO postgres")
        cur.execute("DROP OWNED BY cvscreening_user")
        cur.execute("DROP USER cvscreening_user")
        print("Existing user 'cvscreening_user' dropped.")

    # Create user
    cur.execute("CREATE USER cvscreening_user WITH PASSWORD 'cvscreening_user'")
    print("User 'cvscreening_user' created.")

    # Create database
    cur.execute("CREATE DATABASE cvscreening")
    print("Database 'cvscreening' created.")

    # Grant privileges
    cur.execute("GRANT ALL PRIVILEGES ON DATABASE cvscreening TO cvscreening_user")
    print("Privileges granted to 'cvscreening_user'.")

    cur.close()
    conn.close()

def create_tables():
    # Database connection string
    SQLALCHEMY_DATABASE_URL = "postgresql://cvscreening_user:cvscreening_user@localhost/cvscreening"

    # Create SQLAlchemy engine
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    print("All tables created successfully!")

if __name__ == "__main__":
    setup_postgres()
    create_tables()
    