import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    schema = [
        """CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            city TEXT,
            preferences TEXT,
            preferred_locations TEXT,
            portfolio_value_preference_inr REAL
        )""",
        """CREATE TABLE properties (
            property_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            property_type TEXT NOT NULL,
            sub_type TEXT NOT NULL,
            location TEXT NOT NULL,
            area_sqft REAL NOT NULL,
            current_estimated_value_inr REAL NOT NULL,
            purchase_price_inr REAL,
            annual_rent_inr REAL,
            occupancy_status TEXT NOT NULL,
            tenant_status TEXT NOT NULL,
            ownership_percent REAL NOT NULL,
            status TEXT NOT NULL
        )""",
        """CREATE TABLE conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            flagged_for_attention BOOLEAN NOT NULL DEFAULT FALSE
        )""",
        """CREATE TABLE tool_activity (
            activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            succeeded BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    ]
    for statement in schema:
        db.execute(text(statement))
    db.execute(text("INSERT INTO users (user_id, name, city) VALUES ('U001', 'Asha', 'Mumbai')"))
    db.execute(text("INSERT INTO users (user_id, name, city) VALUES ('U002', 'Dev', 'Pune')"))
    db.execute(text("""
        INSERT INTO properties (
            property_id, user_id, property_type, sub_type, location, area_sqft,
            current_estimated_value_inr, purchase_price_inr, annual_rent_inr,
            occupancy_status, tenant_status, ownership_percent, status
        ) VALUES (
            'P001', 'U001', 'Residential', 'Apartment', 'Mumbai', 800,
            10000000, NULL, 300000, 'Occupied', 'Tenant occupied', 100, 'Active'
        )
    """))
    db.execute(text("""
        INSERT INTO properties (
            property_id, user_id, property_type, sub_type, location, area_sqft,
            current_estimated_value_inr, purchase_price_inr, annual_rent_inr,
            occupancy_status, tenant_status, ownership_percent, status
        ) VALUES (
            'P002', 'U002', 'Residential', 'Apartment', 'Pune', 900,
            99000000, 80000000, 500000, 'Vacant', 'No tenant', 100, 'Active'
        )
    """))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()