"""Database connection and initialization module for PostgreSQL."""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_USER = os.getenv("DB_USERNAME", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "root")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "qa_database")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

Base = declarative_base()


def ensure_database_exists():
    """Check if qa_database exists on PostgreSQL, and create it if it doesn't."""
    try:
        # Connect to maintenance database 'postgres' first
        conn = psycopg2.connect(
            dbname="postgres",
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"[DB] Database '{DB_NAME}' created successfully.")
        else:
            print(f"[DB] Database '{DB_NAME}' already exists.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB Warning] Could not verify/create database via psycopg2: {e}")


# Initialize Engine and Session
try:
    ensure_database_exists()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    print(f"[DB Error] Failed to create database engine: {e}")
    engine = None
    SessionLocal = None


def get_db():
    """FastAPI dependency for database sessions."""
    if SessionLocal is None:
        raise RuntimeError("Database connection is not available.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    if engine is not None:
        import src.db.models  # Ensure models are loaded
        Base.metadata.create_all(bind=engine)
        print("[DB] All tables initialized successfully in PostgreSQL.")
