import re

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_portfolio_summary(db: Session, user_id: str | None = None):
    user_filter = "WHERE user_id = :user_id" if user_id else ""
    result = db.execute(
        text(f"""
            SELECT
                COUNT(*) AS property_count,
                COALESCE(SUM(current_estimated_value_inr), 0) AS total_value
            FROM properties
            {user_filter}
        """)
        , {"user_id": user_id} if user_id else {}
    ).mappings().first()

    return {
        "property_count": result["property_count"],
        "total_estimated_value_inr": result["total_value"]
    }


def get_portfolio_by_location(db: Session, user_id: str | None = None):
    user_filter = "WHERE user_id = :user_id" if user_id else ""
    result = db.execute(
        text(f"""
            SELECT
                location,
                COUNT(*) AS property_count,
                COALESCE(SUM(current_estimated_value_inr), 0)
                    AS total_value_inr
            FROM properties
            {user_filter}
            GROUP BY location
            ORDER BY total_value_inr DESC
        """),
        {"user_id": user_id} if user_id else {}
    ).mappings().all()

    return {
        "locations": [dict(row) for row in result]
    }


def get_portfolio_rent(db: Session, user_id: str | None = None):
    user_filter = "WHERE user_id = :user_id" if user_id else ""
    result = db.execute(
        text(f"""
            SELECT
                property_id,
                location,
                annual_rent_inr,
                current_estimated_value_inr,
                occupancy_status
            FROM properties
            {user_filter}
            ORDER BY annual_rent_inr DESC
        """),
        {"user_id": user_id} if user_id else {}
    ).mappings().all()

    total_rent = sum(
        row["annual_rent_inr"] or 0
        for row in result
    )

    return {
        "total_annual_rent_inr": total_rent,
        "properties": [dict(row) for row in result]
    }

def get_property(
    db: Session,
    property_id: str,
    user_id: str | None = None
):
    owner_filter = "AND user_id = :user_id" if user_id else ""
    result = db.execute(
        text(f"""
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
            WHERE property_id = :property_id
            {owner_filter}
        """),
        {"property_id": property_id, "user_id": user_id}
    ).mappings().first()

    if not result:
        return None

    return dict(result)


def add_property(db: Session, property_data: dict):
    user_exists = db.execute(
        text("SELECT 1 FROM users WHERE user_id = :user_id"),
        {"user_id": property_data["user_id"]}
    ).first()
    if not user_exists:
        return None

    existing_ids = db.execute(
        text("SELECT property_id FROM properties")
    ).scalars().all()
    numeric_ids = [
        int(existing_id[1:])
        for existing_id in existing_ids
        if existing_id and re.fullmatch(r"P\d+", existing_id)
    ]
    next_number = max(numeric_ids, default=0) + 1
    property_id = f"P{next_number:03d}"
    while property_id in existing_ids:
        next_number += 1
        property_id = f"P{next_number:03d}"

    values = {**property_data, "property_id": property_id}
    db.execute(
        text("""
            INSERT INTO properties (
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
            ) VALUES (
                :property_id,
                :user_id,
                :property_type,
                :sub_type,
                :location,
                :area_sqft,
                :current_estimated_value_inr,
                :purchase_price_inr,
                :annual_rent_inr,
                :occupancy_status,
                :tenant_status,
                :ownership_percent,
                :status
            )
        """),
        values
    )
    db.commit()
    return get_property(db, property_id)


def update_property(
    db: Session,
    property_id: str,
    user_id: str,
    updates: dict
):
    allowed_fields = {
        "current_estimated_value_inr",
        "purchase_price_inr",
        "annual_rent_inr",
        "location",
        "area_sqft",
        "occupancy_status",
        "tenant_status",
        "ownership_percent",
        "status"
    }
    changes = {
        field: value
        for field, value in updates.items()
        if field in allowed_fields
    }
    if not changes:
        return get_property(db, property_id, user_id)

    assignments = ", ".join(
        f"{field} = :{field}"
        for field in changes
    )
    result = db.execute(
        text(f"""
            UPDATE properties
            SET {assignments}
            WHERE property_id = :property_id AND user_id = :user_id
        """),
        {
            **changes,
            "property_id": property_id,
            "user_id": user_id
        }
    )
    if result.rowcount == 0:
        db.rollback()
        return None

    db.commit()
    return get_property(db, property_id, user_id)


def get_user(db: Session, user_id: str):
    result = db.execute(
        text("""
            SELECT
                user_id,
                name,
                city,
                preferences,
                preferred_locations,
                portfolio_value_preference_inr
            FROM users
            WHERE user_id = :user_id
        """),
        {"user_id": user_id}
    ).mappings().first()
    return dict(result) if result else None


def get_user_properties(db: Session, user_id: str):
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
    return [dict(row) for row in result]


def list_users(db: Session):
    result = db.execute(
        text("SELECT user_id, name, city FROM users ORDER BY user_id")
    ).mappings().all()
    return [dict(row) for row in result]


def list_conversations(db: Session, limit: int = 100):
    result = db.execute(
        text("""
            SELECT
                conversation_id,
                user_id,
                user_message,
                assistant_response,
                created_at,
                flagged_for_attention
            FROM conversations
            ORDER BY conversation_id DESC
            LIMIT :limit
        """),
        {"limit": limit}
    ).mappings().all()
    return [dict(row) for row in result]


def get_conversation(db: Session, conversation_id: int):
    result = db.execute(
        text("""
            SELECT
                conversation_id,
                user_id,
                user_message,
                assistant_response,
                created_at,
                flagged_for_attention
            FROM conversations
            WHERE conversation_id = :conversation_id
        """),
        {"conversation_id": conversation_id}
    ).mappings().first()
    return dict(result) if result else None


def flag_conversation(db: Session, conversation_id: int, flagged: bool):
    result = db.execute(
        text("""
            UPDATE conversations
            SET flagged_for_attention = :flagged
            WHERE conversation_id = :conversation_id
        """),
        {"conversation_id": conversation_id, "flagged": flagged}
    )
    if result.rowcount == 0:
        db.rollback()
        return None
    db.commit()
    return get_conversation(db, conversation_id)


def get_tool_activity(db: Session, limit: int = 100):
    result = db.execute(
        text("""
            SELECT activity_id, user_id, tool_name, succeeded, created_at
            FROM tool_activity
            ORDER BY activity_id DESC
            LIMIT :limit
        """),
        {"limit": limit}
    ).mappings().all()
    return [dict(row) for row in result]


def log_tool_activity(
    db: Session,
    user_id: str,
    tool_name: str,
    succeeded: bool
):
    try:
        db.execute(
            text("""
                INSERT INTO tool_activity (user_id, tool_name, succeeded)
                VALUES (:user_id, :tool_name, :succeeded)
            """),
            {
                "user_id": user_id,
                "tool_name": tool_name,
                "succeeded": succeeded
            }
        )
        db.commit()
    except Exception:
        db.rollback()