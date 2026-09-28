import re
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.tools import (
    get_portfolio_summary,
    get_portfolio_by_location,
    get_portfolio_rent,
    get_property,
    get_user,
    add_property,
    update_property,
    log_tool_activity
)


class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    user_id: str
    message: str
    response: str
    tool_name: Optional[str] = None


def _amount_value(raw_amount: str, unit: str = "") -> float:
    amount = float(raw_amount.replace(",", ""))
    multiplier = {
        "lakh": 100_000,
        "lac": 100_000,
        "crore": 10_000_000,
        "cr": 10_000_000,
        "k": 1_000
    }.get(unit.lower(), 1)
    return amount * multiplier


def _find_amount(message: str, pattern: str):
    match = re.search(pattern, message, re.IGNORECASE)
    if not match:
        return None
    return _amount_value(match.group(1), match.group(2) or "")


def _property_draft(message: str) -> dict:
    fields = {}
    lower_message = message.lower()

    property_type = re.search(r"\b(residential|commercial|industrial)\b", lower_message)
    subtype = re.search(r"\b(apartment|flat|villa|house|office|shop|warehouse)\b", lower_message)
    if property_type:
        fields["property_type"] = property_type.group(1).title()
    if subtype:
        fields["sub_type"] = subtype.group(1).title()
        if not property_type and subtype.group(1) in {"apartment", "flat", "villa", "house"}:
            fields["property_type"] = "Residential"

    area = re.search(r"([\d,.]+)\s*(?:sq\.?\s*ft|sqft|square feet)", lower_message)
    if area:
        fields["area_sqft"] = float(area.group(1).replace(",", ""))

    value = _find_amount(
        message,
        r"(?:worth|valued?\s+at|current\s+value(?:\s+of)?|value(?:\s+of)?)\s*₹?\s*([\d,.]+)\s*(lakh|lac|crore|cr|k)?"
    )
    if value is not None:
        fields["current_estimated_value_inr"] = value

    rent = _find_amount(
        message,
        r"(?:annual\s+)?rent(?:al\s+income)?\s*(?:is|of|to|=)?\s*₹?\s*([\d,.]+)\s*(lakh|lac|crore|cr|k)?"
    )
    if rent is not None:
        fields["annual_rent_inr"] = rent

    location = re.search(
        r"\bin\s+(.+?)(?=,\s*[\d,.]+\s*(?:sq|square)|\s+[\d,.]+\s*(?:sq|square)|,\s*(?:worth|valued)|\s+(?:with\s+)?(?:area|current\s+value|purchase\s+price|annual\s+rent)\b)",
        message,
        re.IGNORECASE
    )
    if location:
        fields["location"] = location.group(1).strip(" ,.")

    for key, expression in {
        "occupancy_status": r"\b(occupied|vacant|under construction)\b",
        "tenant_status": r"\b(tenant occupied|tenant vacant|owner occupied|no tenant|tenanted|tenant)\b",
        "status": r"\b(active|owned|listed|sold|inactive)\b"
    }.items():
        match = re.search(expression, lower_message)
        if match:
            fields[key] = match.group(1).title()

    ownership = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:ownership|share)?", lower_message)
    if ownership:
        fields["ownership_percent"] = float(ownership.group(1))

    purchase = _find_amount(
        message,
        r"purchase\s+price\s*(?:is|of|to|=)?\s*₹?\s*([\d,.]+)\s*(lakh|lac|crore|cr|k)?"
    )
    if purchase is not None:
        fields["purchase_price_inr"] = purchase
    return fields


def _format_property_details(property_data: dict) -> str:
    purchase_price = property_data.get("purchase_price_inr")
    purchase_text = (
        f"₹{purchase_price:,.2f}"
        if purchase_price is not None
        else "Not available"
    )
    rent = property_data.get("annual_rent_inr")
    rent_text = f"₹{rent:,.2f}" if rent is not None else "Not available"
    return (
        f"Property {property_data['property_id']} is a "
        f"{property_data['property_type']} ({property_data['sub_type']}) in "
        f"{property_data['location']}. Area: {property_data['area_sqft']} sq ft; "
        f"current estimated value: ₹{property_data['current_estimated_value_inr']:,.2f}; "
        f"purchase price: {purchase_text}; "
        f"annual rent: {rent_text}; "
        f"ownership: {property_data['ownership_percent']}%; "
        f"occupancy: {property_data['occupancy_status']}; "
        f"tenant status: {property_data['tenant_status']}; "
        f"status: {property_data['status']}."
    )


def _recent_property_id(history: list) -> Optional[str]:
    for item in history:
        match = re.search(r"\bP[A-Z0-9]+\b", item["user_message"].upper())
        if match:
            return match.group(0)
    return None


def _build_response(user_id: str, message: str, response: str, tool_name: str):
    return ChatResponse(
        user_id=user_id,
        message=message,
        response=response,
        tool_name=tool_name
    )


def process_chat(request: ChatRequest, db: Session):
    message = request.message.lower()
    user = get_user(db, request.user_id)
    if not user:
        return _build_response(
            request.user_id, request.message,
            "I couldn't find that user account.", "get_user"
        )

    history = get_conversation_history(db, request.user_id)
    latest_assistant = history[0]["assistant_response"].lower() if history else ""
    previous_messages = [item["user_message"] for item in history]
    is_hypothetical = any(
        phrase in message
        for phrase in ("what if", "hypothetically", "suppose i", "if i buy", "if i sell")
    )
    property_match = re.search(r"\bP\d+\b", request.message.upper())
    property_id = property_match.group(0) if property_match else None

    if is_hypothetical:
        property_id = property_id or _recent_property_id(history)
        amount = _find_amount(
            request.message,
            r"(?:for|earns?|rent(?:al)?(?:\s+of)?|at)\s*₹?\s*([\d,.]+)\s*(lakh|lac|crore|cr|k)?"
        )
        value_change = re.search(
            r"\b(increase|increased|increases|rise|rises|rose|decrease|decreased|decreases|drop|drops|dropped|fall|falls|fell)\b"
            r".*?\bvalue\b.*?\bby\s+(\d+(?:\.\d+)?)\s*%",
            message
        )
        if property_id and value_change:
            property_data = get_property(db, property_id, request.user_id)
            if not property_data:
                response = f"I couldn't find property {property_id} in your portfolio."
            else:
                current_value = property_data["current_estimated_value_inr"]
                if current_value is None:
                    response = (
                        f"I can't calculate this hypothetical scenario because "
                        f"the current estimated value for {property_id} is not available."
                    )
                else:
                    direction = value_change.group(1)
                    percentage = float(value_change.group(2))
                    is_decrease = direction.startswith(("decreas", "drop", "fall"))
                    factor = 1 - percentage / 100 if is_decrease else 1 + percentage / 100
                    hypothetical_value = float(current_value) * factor
                    change_word = "decreased" if is_decrease else "increased"
                    response = (
                        f"Hypothetical scenario only: if {property_id}'s current "
                        f"estimated value of ₹{float(current_value):,.2f} {change_word} "
                        f"by {percentage:g}%, its hypothetical value would be "
                        f"₹{hypothetical_value:,.2f}. No database data was changed."
                    )
            return _build_response(
                request.user_id,
                request.message,
                response,
                "hypothetical_value_change"
            )

        if property_id and "sell" in message:
            property_data = get_property(db, property_id, request.user_id)
            if not property_data:
                response = f"I couldn't find property {property_id} in your portfolio."
            else:
                summary = get_portfolio_summary(db, request.user_id)
                value = property_data["current_estimated_value_inr"] or 0
                projected = summary["total_estimated_value_inr"] - value
                response = (
                    f"Hypothetical scenario only: if you sold {property_id} at its "
                    f"current estimated value of ₹{value:,.2f}, your portfolio's "
                    f"estimated value after removing it would be ₹{projected:,.2f}. "
                    "No database data was changed."
                )
            return _build_response(request.user_id, request.message, response, "hypothetical_sale")

        if property_id and ("rent" in message or "earn" in message) and amount is not None:
            property_data = get_property(db, property_id, request.user_id)
            if not property_data:
                response = f"I couldn't find property {property_id} in your portfolio."
            else:
                rent = get_portfolio_rent(db, request.user_id)
                existing = property_data["annual_rent_inr"] or 0
                projected = rent["total_annual_rent_inr"] - existing + amount
                response = (
                    f"Hypothetical scenario only: if {property_id} earned "
                    f"₹{amount:,.2f} per year, your portfolio's annual rent "
                    f"would be ₹{projected:,.2f}. No database data was changed."
                )
            return _build_response(request.user_id, request.message, response, "hypothetical_rent")

        if any(word in message for word in ("buy", "purchase", "another property")) and amount is not None:
            summary = get_portfolio_summary(db, request.user_id)
            projected = summary["total_estimated_value_inr"] + amount
            response = (
                f"Hypothetical scenario only: assuming the full purchase amount is "
                f"added to your portfolio, its estimated value would be "
                f"₹{projected:,.2f}. This does not estimate rental income or costs, "
                "and no database data was changed."
            )
            return _build_response(request.user_id, request.message, response, "hypothetical_purchase")

        return _build_response(
            request.user_id,
            request.message,
            "I can calculate a hypothetical purchase, sale, or rent change. "
            "Please include the property ID or the purchase/rent amount.",
            "hypothetical_clarification"
        )

    # Continue a property-add request only when the last assistant turn asked for fields.
    draft_messages = [request.message]
    if latest_assistant.startswith("to complete this property"):
        for prior_message in previous_messages:
            draft_messages.append(prior_message)
            if "add property" in prior_message.lower() or "add a " in prior_message.lower():
                break
    is_add_request = "add" in message and any(
        word in message
        for word in ("property", "apartment", "flat", "villa", "house", "office", "shop")
    )
    if is_add_request or latest_assistant.startswith("to complete this property"):
        fields = {}
        for draft_message in reversed(draft_messages):
            fields.update(_property_draft(draft_message))
        fields["user_id"] = request.user_id
        required = {
            "property_type": "property type",
            "sub_type": "property subtype",
            "location": "location",
            "area_sqft": "area in square feet",
            "current_estimated_value_inr": "current estimated value",
            "annual_rent_inr": "annual rent",
            "occupancy_status": "occupancy status",
            "tenant_status": "tenant status",
            "ownership_percent": "ownership percentage",
            "status": "property status"
        }
        missing = [label for field, label in required.items() if field not in fields]
        if missing:
            response = (
                "To complete this property, please provide: "
                + ", ".join(missing)
                + "."
            )
            return _build_response(request.user_id, request.message, response, "add_property")
        created = add_property(db, fields)
        if not created:
            response = "I couldn't find that user account, so the property was not added."
        else:
            response = f"Added property {created['property_id']} to your portfolio."
        return _build_response(request.user_id, request.message, response, "add_property")

    # Property updates change only values explicitly included in the message.
    if property_id and any(word in message for word in ("update", "change", "set")):
        updates = {}
        rent_amount = _find_amount(
            request.message,
            r"\b(?:annual\s+)?rent\b.*?\b(?:to|=)\s*₹?\s*([\d,.]+)\s*(lakh|lac|crore|cr|k)?"
        )
        value_amount = _find_amount(
            request.message,
            r"\b(?:current\s+estimated\s+)?(?:value|worth)\b.*?\b(?:to|=)\s*₹?\s*([\d,.]+)\s*(lakh|lac|crore|cr|k)?"
        )
        if rent_amount is not None:
            updates["annual_rent_inr"] = rent_amount
        if value_amount is not None:
            updates["current_estimated_value_inr"] = value_amount
        purchase_amount = _find_amount(
            request.message,
            r"\bpurchase\s+price\b.*?\b(?:to|=)\s*₹?\s*([\d,.]+)\s*(lakh|lac|crore|cr|k)?"
        )
        if purchase_amount is not None:
            updates["purchase_price_inr"] = purchase_amount
        location = re.search(
            r"\blocation\b.*?\b(?:to|=)\s*(.+)$",
            request.message,
            re.IGNORECASE
        )
        if location:
            updates["location"] = location.group(1).strip()
        area = re.search(
            r"\barea\b.*?\b(?:to|=)\s*([\d,.]+)",
            request.message,
            re.IGNORECASE
        )
        if area:
            updates["area_sqft"] = float(area.group(1).replace(",", ""))
        for field, expression in {
            "occupancy_status": r"occupancy(?: status)?\s+(?:to|=)\s*(occupied|vacant|under construction)",
            "tenant_status": r"tenant(?: status)?\s+(?:to|=)\s*(tenant occupied|tenanted|owner occupied|no tenant|tenant vacant)",
            "status": r"status\s+(?:to|=)\s*(active|owned|listed|sold|inactive)"
        }.items():
            match = re.search(expression, request.message, re.IGNORECASE)
            if match:
                updates[field] = match.group(1).title()
        ownership = re.search(
            r"ownership(?: percent(?:age)?)?\s+(?:to|=)\s*(\d+(?:\.\d+)?)\s*%?",
            request.message,
            re.IGNORECASE
        )
        if ownership:
            updates["ownership_percent"] = float(ownership.group(1))
        if not updates:
            response = "Please specify a supported property field and its new value."
        else:
            updated = update_property(db, property_id, request.user_id, updates)
            response = (
                f"Updated property {property_id}. " + _format_property_details(updated)
                if updated
                else f"I couldn't find property {property_id} in your portfolio."
            )
        return _build_response(request.user_id, request.message, response, "update_property")

    if property_id:
        property_data = get_property(db, property_id, request.user_id)
        if property_data:
            response = _format_property_details(property_data)
        else:
            response = f"I couldn't find property {property_id} in your portfolio."
        return _build_response(request.user_id, request.message, response, "get_property")

    if "portfolio value" in message or "total value" in message or "portfolio summary" in message:
        summary = get_portfolio_summary(db, request.user_id)
        response = (
            f"Your portfolio has {summary['property_count']} properties with a "
            f"total estimated value of ₹{summary['total_estimated_value_inr']:,}."
        )
        return _build_response(request.user_id, request.message, response, "get_portfolio_summary")

    location_follow_up = any(word in message for word in ("highest", "lowest", "which one")) and (
        "location" in latest_assistant or "portfolio by location" in latest_assistant
    )
    if "location" in message or "locations" in message or location_follow_up:
        locations = get_portfolio_by_location(db, request.user_id)["locations"]
        if not locations:
            response = "Your portfolio does not have any properties yet."
        elif "highest" in message:
            item = locations[0]
            response = f"The highest-value location is {item['location']} at ₹{item['total_value_inr']:,.2f}."
        elif "lowest" in message:
            item = locations[-1]
            response = f"The lowest-value location is {item['location']} at ₹{item['total_value_inr']:,.2f}."
        else:
            details = ", ".join(
                f"{item['location']}: ₹{item['total_value_inr']:,}"
                for item in locations
            )
            response = f"Your portfolio by location is: {details}"
        return _build_response(request.user_id, request.message, response, "get_portfolio_by_location")

    property_id = _recent_property_id(history)
    if property_id and any(word in message for word in ("its", "annual rent", "purchase price", "occupancy", "tenant")):
        property_data = get_property(db, property_id, request.user_id)
        if property_data:
            response = _format_property_details(property_data)
            return _build_response(request.user_id, request.message, response, "get_property")

    if "rent" in message or "rental income" in message:
        rent = get_portfolio_rent(db, request.user_id)
        response = f"Your total annual rental income is ₹{rent['total_annual_rent_inr']:,}."
        return _build_response(request.user_id, request.message, response, "get_portfolio_rent")

    return _build_response(
        request.user_id,
        request.message,
        "I can answer questions about your portfolio value, locations, rent, "
        "property details, and simple hypothetical purchase, sale, or rent scenarios.",
        "rule_based_fallback"
    )


def save_conversation(
    db: Session,
    user_id: str,
    user_message: str,
    assistant_response: str
):
    db.execute(
        text("""
            INSERT INTO conversations
            (user_id, user_message, assistant_response)
            VALUES (:user_id, :user_message, :assistant_response)
        """),
        {
            "user_id": user_id,
            "user_message": user_message,
            "assistant_response": assistant_response
        }
    )

    db.commit()


def process_and_save_chat(request: ChatRequest, db: Session):
    response = process_chat(request, db)

    log_tool_activity(
        db,
        request.user_id,
        response.tool_name or "rule_based_fallback",
        True
    )

    save_conversation(
        db,
        request.user_id,
        request.message,
        response.response
    )

    return response


def get_conversation_history(
    db: Session,
    user_id: str,
    limit: int = 5
):
    result = db.execute(
        text("""
            SELECT
                user_message,
                assistant_response,
                created_at
            FROM conversations
            WHERE user_id = :user_id
            ORDER BY conversation_id DESC
            LIMIT :limit
        """),
        {
            "user_id": user_id,
            "limit": limit
        }
    ).mappings().all()

    return [dict(row) for row in result]

