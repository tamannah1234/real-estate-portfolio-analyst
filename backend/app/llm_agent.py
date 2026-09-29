import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.tools import (
    add_property,
    get_portfolio_by_location,
    get_portfolio_rent,
    get_portfolio_summary,
    get_highest_value_property,
    get_property,
    hypothetical_value_change,
    update_property
)


OPENROUTER_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_summary",
            "description": "Get the selected user's actual portfolio property count and total estimated value.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_by_location",
            "description": "Get the selected user's actual portfolio value grouped by location.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_rent",
            "description": "Get the selected user's actual annual rental income and rent by property only. Do not use for current estimated value or property-value ranking questions.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_highest_value_property",
            "description": "Find the selected user's property with the highest non-null current estimated value. Use for questions asking which property is most valuable or has the highest current estimated value.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_property",
            "description": "Get a property owned by the selected user. Never look up another user's property.",
            "parameters": {
                "type": "object",
                "properties": {"property_id": {"type": "string"}},
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_property",
            "description": "Add a property for the selected user. Supply all required fields; if information is missing, use continue_rule_based so the existing chat can ask for it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_type": {"type": "string"},
                    "sub_type": {"type": "string"},
                    "location": {"type": "string"},
                    "area_sqft": {"type": "number"},
                    "current_estimated_value_inr": {"type": "number"},
                    "purchase_price_inr": {"type": ["number", "null"]},
                    "annual_rent_inr": {"type": "number"},
                    "occupancy_status": {"type": "string"},
                    "tenant_status": {"type": "string"},
                    "ownership_percent": {"type": "number"},
                    "status": {"type": "string"}
                },
                "required": [
                    "property_type", "sub_type", "location", "area_sqft",
                    "current_estimated_value_inr", "annual_rent_inr",
                    "occupancy_status", "tenant_status", "ownership_percent", "status"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_property",
            "description": "Update only explicitly supplied fields on a property owned by the selected user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "string"},
                    "current_estimated_value_inr": {"type": "number"},
                    "purchase_price_inr": {"type": ["number", "null"]},
                    "annual_rent_inr": {"type": "number"},
                    "location": {"type": "string"},
                    "area_sqft": {"type": "number"},
                    "occupancy_status": {"type": "string"},
                    "tenant_status": {"type": "string"},
                    "ownership_percent": {"type": "number"},
                    "status": {"type": "string"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hypothetical_value_change",
            "description": "Calculate a hypothetical percentage change to a selected user's property's current estimated value. This is read-only and must be labeled hypothetical.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "string"},
                    "percentage_change": {"type": "number", "description": "Signed percentage; for example 10 means +10 and -10 means -10."}
                },
                "required": ["property_id", "percentage_change"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "continue_rule_based",
            "description": "Use existing deterministic chat handling for hypothetical purchase, sale, or rent scenarios, follow-up clarification, or requests not covered by the other tools.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

ALLOWED_TOOL_NAMES = {
    definition["function"]["name"]
    for definition in TOOL_DEFINITIONS
}

SYSTEM_PROMPT = """You are the intent interpreter for a real-estate portfolio analyst.
Select exactly one approved backend tool for each request. Use recent conversation turns to resolve simple follow-ups.
Actual financial facts must come from tools. Never invent property or portfolio data.
Never request a user_id in tool arguments; the backend supplies and authorizes the selected user.
Never suggest or execute SQL. Do not call a write tool for a hypothetical scenario.
Use hypothetical_value_change only for read-only property value scenarios and preserve its hypothetical label.
Use continue_rule_based for hypothetical purchase, sale, or rent requests, clarification, or anything not covered by another tool.
If a request is missing required add-property information, continue_rule_based so the existing chat can ask for it.
"""


class AddPropertyArguments(BaseModel):
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


class UpdatePropertyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: str = Field(min_length=1)
    current_estimated_value_inr: Optional[float] = Field(default=None, ge=0)
    purchase_price_inr: Optional[float] = Field(default=None, ge=0)
    annual_rent_inr: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = Field(default=None, min_length=1)
    area_sqft: Optional[float] = Field(default=None, gt=0)
    occupancy_status: Optional[str] = Field(default=None, min_length=1)
    tenant_status: Optional[str] = Field(default=None, min_length=1)
    ownership_percent: Optional[float] = Field(default=None, gt=0, le=100)
    status: Optional[str] = Field(default=None, min_length=1)


class PropertyLookupArguments(BaseModel):
    property_id: str = Field(min_length=1)


class HypotheticalValueArguments(BaseModel):
    property_id: str = Field(min_length=1)
    percentage_change: float = Field(ge=-100)


def _create_model(api_key: str):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        timeout=20,
        max_retries=0
    ).bind_tools(TOOL_DEFINITIONS)


def select_tool(user_id: str, message: str, history: list) -> Optional[dict]:
    """Ask OpenRouter for one approved tool selection; return None to use rule-based chat."""
    load_dotenv(OPENROUTER_ENV_FILE)
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        model = _create_model(api_key)
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for turn in reversed(history):
            messages.append(HumanMessage(content=turn["user_message"]))
            messages.append(AIMessage(content=turn["assistant_response"]))
        messages.append(HumanMessage(content=f"Selected user: {user_id}\nRequest: {message}"))
        result = model.invoke(messages)
    except Exception:
        return None

    tool_calls = getattr(result, "tool_calls", [])
    if len(tool_calls) != 1:
        return None

    selected = tool_calls[0]
    tool_name = selected.get("name")
    arguments = selected.get("args")
    if tool_name not in ALLOWED_TOOL_NAMES or not isinstance(arguments, dict):
        return None
    return {"name": tool_name, "arguments": arguments}


def execute_tool(db, user_id: str, selection: dict):
    """Execute one selected tool through the backend's approved database helpers."""
    tool_name = selection["name"]
    arguments = selection["arguments"]

    if tool_name == "continue_rule_based":
        return None
    if tool_name == "get_portfolio_summary":
        return tool_name, get_portfolio_summary(db, user_id)
    if tool_name == "get_portfolio_by_location":
        return tool_name, get_portfolio_by_location(db, user_id)
    if tool_name == "get_portfolio_rent":
        return tool_name, get_portfolio_rent(db, user_id)
    if tool_name == "get_highest_value_property":
        return tool_name, get_highest_value_property(db, user_id)
    if tool_name == "get_property":
        parsed = PropertyLookupArguments.model_validate(arguments)
        return tool_name, get_property(db, parsed.property_id, user_id)
    if tool_name == "add_property":
        required_labels = {
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
        missing = [
            label
            for field, label in required_labels.items()
            if arguments.get(field) is None or arguments.get(field) == ""
        ]
        if missing:
            return (
                tool_name,
                "To complete this property, please provide: "
                + ", ".join(missing)
                + "."
            )
        try:
            parsed = AddPropertyArguments.model_validate(arguments)
        except ValidationError:
            return tool_name, "Some property details are invalid. Please check the values and try again."
        property_data = parsed.model_dump()
        property_data["user_id"] = user_id
        return tool_name, add_property(db, property_data)
    if tool_name == "update_property":
        parsed = UpdatePropertyArguments.model_validate(arguments)
        updates = parsed.model_dump(exclude_unset=True, exclude={"property_id"})
        if not updates:
            return tool_name, "Please specify at least one property field to update."
        return tool_name, update_property(
            db,
            parsed.property_id,
            user_id,
            updates
        )
    if tool_name == "hypothetical_value_change":
        parsed = HypotheticalValueArguments.model_validate(arguments)
        return tool_name, hypothetical_value_change(
            db,
            parsed.property_id,
            user_id,
            parsed.percentage_change
        )

    return None

def validate_tool_selection(message: str, selected_tool: str) -> str:
    """Validate obvious intent/tool mismatches before execution."""
    text = message.lower()

    if (
        "highest" in text
        and ("value" in text or "valuable" in text)
        and selected_tool != "get_highest_value_property"
    ):
        return "get_highest_value_property"

    if (
        ("rent" in text or "rental income" in text)
        and "highest" not in text
        and selected_tool != "get_portfolio_rent"
    ):
        return "get_portfolio_rent"

    if (
        ("portfolio value" in text or "total value" in text)
        and selected_tool != "get_portfolio_summary"
    ):
        return "get_portfolio_summary"

    return selected_tool