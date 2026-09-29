from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db

from app.tools import (
    get_portfolio_summary,
    get_portfolio_by_location,
    get_portfolio_rent,
    add_property,
    update_property,
    get_property as find_property,
    get_user as find_user,
    get_user_properties as find_user_properties,
    list_users,
    list_conversations,
    get_conversation,
    flag_conversation,
    get_tool_activity,
    log_tool_activity
)

from app.chat import (
    ChatRequest,
    ChatResponse,
    process_and_save_chat,
    get_conversation_history
)

app = FastAPI(
    title="Real Estate Portfolio Analyst"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                    "https://real-estate-portfolio-frontend.onrender.com"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["*"]
)


class PropertyCreate(BaseModel):
    user_id: str = Field(min_length=1)
    property_type: str = Field(min_length=1)
    sub_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    area_sqft: float = Field(gt=0)
    current_estimated_value_inr: float = Field(ge=0)
    purchase_price_inr: Optional[float] = Field(default=None, ge=0)
    annual_rent_inr: float = Field(ge=0)
    occupancy_status: str = Field(min_length=1)
    tenant_status: str = Field(min_length=1)
    ownership_percent: float = Field(gt=0, le=100)
    status: str = Field(min_length=1)


class PropertyUpdate(BaseModel):
    current_estimated_value_inr: Optional[float] = Field(default=None, ge=0)
    purchase_price_inr: Optional[float] = Field(default=None, ge=0)
    annual_rent_inr: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = Field(default=None, min_length=1)
    area_sqft: Optional[float] = Field(default=None, gt=0)
    occupancy_status: Optional[str] = Field(default=None, min_length=1)
    tenant_status: Optional[str] = Field(default=None, min_length=1)
    ownership_percent: Optional[float] = Field(default=None, gt=0, le=100)
    status: Optional[str] = Field(default=None, min_length=1)


class ConversationFlag(BaseModel):
    flagged: bool


@app.get("/")
def root():
    return {
        "message": "Real Estate Portfolio Analyst API is running"
    }


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    users_count = db.execute(
        text("SELECT COUNT(*) FROM users")
    ).scalar()

    properties_count = db.execute(
        text("SELECT COUNT(*) FROM properties")
    ).scalar()

    return {
        "database": "connected",
        "users_count": users_count,
        "properties_count": properties_count
    }

@app.get("/portfolio/summary")
def portfolio_summary(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_summary(db, user_id)

@app.get("/properties")
def get_properties(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    result = db.execute(
        text("""
            SELECT
                property_id,
                user_id,
                property_type,
                sub_type,
                location,
                area_sqft,
                current_estimated_value_inr,
                purchase_price_inr,
                annual_rent_inr,
                occupancy_status,
                tenant_status,
                ownership_percent,
                status
            FROM properties
            WHERE user_id = :user_id
            ORDER BY property_id
        """),
        {"user_id": user_id}
    ).mappings().all()

    return {
        "properties": result
    }


@app.post("/properties", status_code=201)
def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db)
):
    try:
        created = add_property(db, property_data.dict())
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save property"
        ) from exc

    if created is None:
        raise HTTPException(status_code=404, detail="User not found")
    log_tool_activity(db, property_data.user_id, "add_property_api", True)
    return created

@app.get("/users/{user_id}/properties")
def get_user_properties(
    user_id: str,
    db: Session = Depends(get_db)
):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user_id,
        "properties": find_user_properties(db, user_id)
    }


@app.get("/users/{user_id}/properties/{property_id}")
def get_owned_property(
    user_id: str,
    property_id: str,
    db: Session = Depends(get_db)
):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    property_data = find_property(db, property_id, user_id)
    if not property_data:
        raise HTTPException(status_code=404, detail="Property not found")
    return property_data

@app.get("/users/{user_id}")
def get_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    result = find_user(db, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result

@app.get("/portfolio/by-location")
def portfolio_by_location(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_by_location(db, user_id)

@app.get("/portfolio/rent")
def portfolio_rent(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_rent(db, user_id)

@app.get("/properties/{property_id}")
def get_property(
    property_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    result = find_property(db, property_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Property not found")
    return result

@app.get("/tools/portfolio-summary")
def tool_portfolio_summary(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_summary(db, user_id)


@app.get("/tools/portfolio-location")
def tool_portfolio_location(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_by_location(db, user_id)


@app.get("/tools/portfolio-rent")
def tool_portfolio_rent(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_rent(db, user_id)

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    return process_and_save_chat(request, db)


@app.get("/conversations/{user_id}")
def conversation_history(
    user_id: str,
    db: Session = Depends(get_db)
):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user_id,
        "conversations": get_conversation_history(db, user_id)
    }


@app.put("/users/{user_id}/properties/{property_id}")
def edit_property(
    user_id: str,
    property_id: str,
    updates: PropertyUpdate,
    db: Session = Depends(get_db)
):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    changes = updates.dict(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No property fields supplied")
    updated = update_property(db, property_id, user_id, changes)
    if not updated:
        raise HTTPException(status_code=404, detail="Property not found")
    log_tool_activity(db, user_id, "update_property_api", True)
    return updated


@app.get("/users/{user_id}/portfolio/summary")
def user_portfolio_summary(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_summary(db, user_id)


@app.get("/users/{user_id}/portfolio/by-location")
def user_portfolio_by_location(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_by_location(db, user_id)


@app.get("/users/{user_id}/portfolio/rent")
def user_portfolio_rent(user_id: str, db: Session = Depends(get_db)):
    if not find_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return get_portfolio_rent(db, user_id)


@app.get("/admin/users")
def admin_users(db: Session = Depends(get_db)):
    return {"users": list_users(db)}


@app.get("/admin/conversations")
def admin_conversations(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="Limit must be between 1 and 500")
    return {"conversations": list_conversations(db, limit)}


@app.get("/admin/conversations/{conversation_id}")
def admin_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.patch("/admin/conversations/{conversation_id}/flag")
def admin_flag_conversation(
    conversation_id: int,
    request: ConversationFlag,
    db: Session = Depends(get_db)
):
    conversation = flag_conversation(db, conversation_id, request.flagged)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.get("/admin/tool-activity")
def admin_tool_activity(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="Limit must be between 1 and 500")
    return {"activity": get_tool_activity(db, limit)}