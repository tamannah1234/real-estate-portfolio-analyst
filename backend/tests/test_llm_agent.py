from types import SimpleNamespace

from langchain_core.messages import AIMessage

from app import llm_agent
from app.chat import ChatRequest, process_chat
from sqlalchemy import text


class FakeModel:
    def __init__(self, result):
        self.result = result
        self.bound_tools = None
        self.messages = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages):
        self.messages = messages
        return self.result


def test_selector_uses_openrouter_tool_call_and_recent_history(monkeypatch):
    fake_model = FakeModel(AIMessage(
        content="",
        tool_calls=[{
            "name": "get_portfolio_summary",
            "args": {},
            "id": "call_summary",
            "type": "tool_call"
        }]
    ))
    monkeypatch.setattr(llm_agent, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(
        llm_agent,
        "_create_model",
        lambda _key: fake_model.bind_tools(llm_agent.TOOL_DEFINITIONS)
    )

    selection = llm_agent.select_tool(
        "U001",
        "How much is it worth?",
        [{"user_message": "What is my portfolio value?", "assistant_response": "..."}]
    )

    assert selection == {"name": "get_portfolio_summary", "arguments": {}}
    assert "How much is it worth?" in fake_model.messages[-1].content
    assert any(
        "What is my portfolio value?" in item.content
        for item in fake_model.messages
    )
    assert any(
        definition["function"]["name"] == "hypothetical_value_change"
        for definition in llm_agent.TOOL_DEFINITIONS
    )


def test_selector_does_not_require_key_or_call_model(monkeypatch):
    monkeypatch.setattr(llm_agent, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        llm_agent,
        "_create_model",
        lambda _key: (_ for _ in ()).throw(AssertionError("model must not be created"))
    )

    assert llm_agent.select_tool("U001", "What is my portfolio value?", []) is None


def test_selector_rejects_unknown_tool_call(monkeypatch):
    fake_model = FakeModel(SimpleNamespace(tool_calls=[{
        "name": "execute_sql",
        "args": {"query": "SELECT 1"},
        "id": "call_bad"
    }]))
    monkeypatch.setattr(llm_agent, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(llm_agent, "_create_model", lambda _key: fake_model)

    assert llm_agent.select_tool("U001", "show data", []) is None


def test_selector_falls_back_when_openrouter_is_unavailable(monkeypatch):
    monkeypatch.setattr(llm_agent, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(
        llm_agent,
        "_create_model",
        lambda _key: (_ for _ in ()).throw(ConnectionError("offline"))
    )

    assert llm_agent.select_tool("U001", "What is my portfolio value?", []) is None


def test_hypothetical_value_tool_is_read_only_and_user_scoped(db_session):
    result = llm_agent.execute_tool(db_session, "U001", {
        "name": "hypothetical_value_change",
        "arguments": {"property_id": "P001", "percentage_change": 10}
    })

    assert result[0] == "hypothetical_value_change"
    assert result[1]["hypothetical_value_inr"] == 11000000
    actual_value = db_session.execute(text(
        "SELECT current_estimated_value_inr FROM properties WHERE property_id = 'P001'"
    )).scalar_one()
    assert actual_value == 10000000

    other_users_property = llm_agent.execute_tool(db_session, "U001", {
        "name": "hypothetical_value_change",
        "arguments": {"property_id": "P002", "percentage_change": 10}
    })
    assert other_users_property == ("hypothetical_value_change", None)


def test_selected_summary_runs_through_backend_tool(monkeypatch, db_session):
    monkeypatch.setattr(llm_agent, "select_tool", lambda *_args: {
        "name": "get_portfolio_summary",
        "arguments": {}
    })

    response = process_chat(
        ChatRequest(user_id="U001", message="What's the size of my portfolio?"),
        db_session
    )

    assert response.tool_name == "get_portfolio_summary"
    assert "1 properties" in response.response
    assert "₹10,000,000" in response.response


def test_highest_value_property_request_uses_scoped_ranking_tool(monkeypatch, db_session):
    db_session.execute(text("""
        INSERT INTO properties (
            property_id, user_id, property_type, sub_type, location, area_sqft,
            current_estimated_value_inr, purchase_price_inr, annual_rent_inr,
            occupancy_status, tenant_status, ownership_percent, status
        ) VALUES (
            'P003', 'U001', 'Residential', 'House', 'Navi Mumbai', 1200,
            25000000, NULL, 0, 'Vacant', 'No tenant', 100, 'Active'
        )
    """))
    db_session.commit()
    fake_model = FakeModel(AIMessage(
        content="",
        tool_calls=[{
            "name": "get_highest_value_property",
            "args": {},
            "id": "call_highest_value",
            "type": "tool_call"
        }]
    ))
    monkeypatch.setattr(llm_agent, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(
        llm_agent,
        "_create_model",
        lambda _key: fake_model.bind_tools(llm_agent.TOOL_DEFINITIONS)
    )

    response = process_chat(
        ChatRequest(
            user_id="U001",
            message="Which property in my portfolio has the highest current estimated value?"
        ),
        db_session
    )

    assert response.tool_name == "get_highest_value_property"
    assert "P003" in response.response
    assert "Navi Mumbai" in response.response
    assert "₹25,000,000.00" in response.response
    assert any(
        definition["function"]["name"] == "get_highest_value_property"
        for definition in fake_model.bound_tools
    )


def test_selected_update_cannot_modify_another_users_property(db_session):
    result = llm_agent.execute_tool(db_session, "U001", {
        "name": "update_property",
        "arguments": {"property_id": "P002", "annual_rent_inr": 999999}
    })

    assert result == ("update_property", None)
    annual_rent = db_session.execute(text(
        "SELECT annual_rent_inr FROM properties WHERE property_id = 'P002'"
    )).scalar_one()
    assert annual_rent == 500000


def test_incomplete_add_tool_asks_for_fields_without_writing(db_session):
    result = llm_agent.execute_tool(db_session, "U001", {
        "name": "add_property",
        "arguments": {
            "property_type": "Residential",
            "sub_type": "Apartment"
        }
    })

    assert result[0] == "add_property"
    assert "location" in result[1]
    count = db_session.execute(text("SELECT COUNT(*) FROM properties")).scalar_one()
    assert count == 2
