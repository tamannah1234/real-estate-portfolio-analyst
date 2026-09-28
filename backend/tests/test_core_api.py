from sqlalchemy import text
import pytest

from app.chat import _property_draft


def test_database_health(client):
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json()["users_count"] == 2
    assert response.json()["properties_count"] == 2


def test_portfolio_summary_is_user_specific(client):
    response = client.get("/users/U001/portfolio/summary")

    assert response.status_code == 200
    assert response.json()["property_count"] == 1
    assert response.json()["total_estimated_value_inr"] == 10000000


def test_property_lookup_hides_another_users_property(client):
    response = client.get("/users/U001/properties/P002")

    assert response.status_code == 404


def test_add_property_creates_new_owned_property(client):
    response = client.post("/properties", json={
        "user_id": "U001",
        "property_type": "Residential",
        "sub_type": "Apartment",
        "location": "Malad East, Mumbai",
        "area_sqft": 850,
        "current_estimated_value_inr": 8000000,
        "annual_rent_inr": 0,
        "occupancy_status": "Vacant",
        "tenant_status": "No tenant",
        "ownership_percent": 100,
        "status": "Active"
    })

    assert response.status_code == 201
    created = response.json()
    assert created["property_id"].startswith("P")
    assert created["purchase_price_inr"] is None
    assert client.get(f"/users/U001/properties/{created['property_id']}").status_code == 200


def test_update_changes_only_explicit_fields(client):
    response = client.put(
        "/users/U001/properties/P001",
        json={"annual_rent_inr": 600000}
    )

    assert response.status_code == 200
    assert response.json()["annual_rent_inr"] == 600000
    assert response.json()["location"] == "Mumbai"


def test_hypothetical_rent_does_not_change_property_data(client, db_session):
    response = client.post("/chat", json={
        "user_id": "U001",
        "message": "What if P001 earns ₹600000 rent per year?"
    })

    assert response.status_code == 200
    assert "Hypothetical scenario only" in response.json()["response"]
    actual_rent = db_session.execute(text(
        "SELECT annual_rent_inr FROM properties WHERE property_id = 'P001'"
    )).scalar_one()
    assert actual_rent == 300000


def test_chat_saves_conversation(client):
    response = client.post("/chat", json={
        "user_id": "U001",
        "message": "What is my portfolio value?"
    })

    assert response.status_code == 200
    history = client.get("/conversations/U001")
    assert history.status_code == 200
    assert history.json()["conversations"][0]["user_message"] == "What is my portfolio value?"


@pytest.mark.parametrize("message", [
    "Tenant status is Tenant",
    "tenant: Tenant",
    "tenant",
    "tenant status Tenant"
])
def test_property_draft_recognizes_tenant_phrases(message):
    assert _property_draft(message)["tenant_status"] == "Tenant"


@pytest.mark.parametrize("message", [
    "property status is Active",
    "status is Active",
    "status: Active",
    "Active"
])
def test_property_draft_recognizes_active_status_phrases(message):
    assert _property_draft(message)["status"] == "Active"


def test_add_property_chat_completes_from_follow_up(client):
    first_response = client.post("/chat", json={
        "user_id": "U001",
        "message": (
            "Add a new residential apartment in Borivali West, Mumbai with "
            "area 900 sq ft, current value 9000000, purchase price 8000000, "
            "annual rent 360000, occupied, tenant, 100% ownership"
        )
    })

    assert first_response.status_code == 200
    assert "property status" in first_response.json()["response"]

    follow_up = client.post("/chat", json={
        "user_id": "U001",
        "message": "Tenant status is Tenant and property status is Active"
    })

    assert follow_up.status_code == 200
    assert follow_up.json()["response"] == "Added property P003 to your portfolio."
    created = client.get("/users/U001/properties/P003")
    assert created.status_code == 200
    assert created.json()["occupancy_status"] == "Occupied"
    assert created.json()["tenant_status"] == "Tenant"
    assert created.json()["status"] == "Active"