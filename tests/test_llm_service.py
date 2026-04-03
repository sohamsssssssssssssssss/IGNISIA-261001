import importlib.util

import pytest


HAS_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None


pytestmark = pytest.mark.skipif(
    not HAS_SQLALCHEMY,
    reason="sqlalchemy is not installed in this environment",
)

if HAS_SQLALCHEMY:
    from app.core import storage as storage_module
    from app.core.database import reset_database_runtime
    from app.core.settings import get_settings
    from app.core.session_store import SessionStore
    from app.services.llm_service import LLMService


class FakeRetrievalService:
    def get_similar_cases(self, gstin, score_payload, k=3):
        return [
            {
                "gstin": "29CASE5678B1Z2",
                "company_name": "Reference Manufacturing Ltd.",
                "credit_score": 701,
                "risk_band": "LOW_RISK",
                "similarity": 0.91,
                "outcome": {"status": "repaid"},
                "key_shap_reasons": [
                    {"feature": "GST Filing Regularity", "reason": "Strong compliance", "shap_value": 0.22},
                ],
            }
        ]

    def get_relevant_rules(self, score_payload, k=5):
        return [
            {
                "id": "rule-1",
                "text": "Manufacturing borrowers with stable GST and UPI patterns often repay on schedule.",
                "similarity": 0.88,
                "metadata": {"doc_type": "association_rule"},
            }
        ]

    def get_context_for_question(self, question, gstin, k=5):
        return [
            {
                "id": "ctx-1",
                "collection": "score_history",
                "similarity": 0.93,
                "text": "Prior approved manufacturing case with score 701 repaid successfully.",
                "metadata": {"source": "score_history"},
            }
        ]


class FakeContextBuilder:
    def get_system_prompt(self):
        return "SYSTEM PROMPT"

    def build_scoring_context(self, gstin, score_payload, similar_cases, rules):
        return (
            f"[BUSINESS PROFILE]\nGSTIN: {gstin}\nScore: {score_payload['credit_score']} | "
            f"Risk band: {score_payload['risk_band']['band']}\n"
            f"Fraud: {score_payload['fraud_detection']['circular_risk']}"
        )

    def build_chat_context(self, gstin, score_payload, similar_cases, rules, conversation_history, new_message):
        history_lines = "\n".join(f"{item['role']}: {item['content']}" for item in conversation_history)
        return (
            f"[BUSINESS PROFILE]\nGSTIN: {gstin}\nScore: {score_payload['credit_score']}\n"
            f"[CONVERSATION HISTORY]\n{history_lines}\n"
            f"[NEW USER MESSAGE]\nUser: {new_message}"
        )


class FakeAnthropicMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        prompt = kwargs["messages"][0]["content"]
        if "3-paragraph underwriting brief" in prompt:
            text = (
                "The borrower scored 742 with LOW_RISK because GST regularity and payment cadence are strong.\n\n"
                "Key risk is limited, with fraud risk LOW and strong compliance signals.\n\n"
                "Recommend proceeding to manual review of policy terms; improving shipment momentum could strengthen the case."
            )
        else:
            text = "With score 742 and fraud risk LOW, I would not give final approval yet; proceed with conditional review."

        class Block:
            def __init__(self, value):
                self.text = value

        class Response:
            def __init__(self, value):
                self.content = [Block(value)]

        return Response(text)


class FakeAnthropicClient:
    def __init__(self):
        self.messages = FakeAnthropicMessages()


def _sample_score_payload():
    return {
        "gstin": "29CLEAN5678B1Z2",
        "company_name": "CleanTech Manufacturing Ltd.",
        "credit_score": 742,
        "risk_band": {"band": "LOW_RISK"},
        "fraud_detection": {"circular_risk": "LOW", "cycle_count": 0},
        "recommendation": {"recommended_amount": 2500000},
        "top_reasons": [{"feature": "GST Filing Regularity", "reason": "Strong compliance", "shap_value": 0.31}],
    }


def test_generate_narrative_returns_text_and_sources(tmp_path, monkeypatch):
    db_path = tmp_path / "llm-narrative.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()

    anthropic_client = FakeAnthropicClient()
    service = LLMService(
        retrieval_service=FakeRetrievalService(),
        context_builder=FakeContextBuilder(),
        session_store=SessionStore(),
        anthropic_client=anthropic_client,
    )

    result = service.generate_narrative("29CLEAN5678B1Z2", _sample_score_payload())

    assert "742" in result["narrative"]
    assert result["model_used"] == "claude-sonnet-4-20250514"
    assert len(result["sources"]) >= 2
    assert anthropic_client.messages.calls[0]["max_tokens"] == 1000


def test_chat_creates_session_and_persists_history(tmp_path, monkeypatch):
    db_path = tmp_path / "llm-chat.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()

    session_store = SessionStore()
    anthropic_client = FakeAnthropicClient()
    service = LLMService(
        retrieval_service=FakeRetrievalService(),
        context_builder=FakeContextBuilder(),
        session_store=session_store,
        anthropic_client=anthropic_client,
    )

    first = service.chat(
        "29CLEAN5678B1Z2",
        _sample_score_payload(),
        "Should I approve this loan?",
        None,
    )

    assert len(first["session_id"]) == 36
    assert "742" in first["reply"]
    assert len(session_store.get_history(first["session_id"])) == 2

    second = service.chat(
        "29CLEAN5678B1Z2",
        _sample_score_payload(),
        "What is the main risk?",
        first["session_id"],
    )

    assert second["session_id"] == first["session_id"]
    assert len(session_store.get_history(first["session_id"])) == 4
    assert anthropic_client.messages.calls[1]["max_tokens"] == 800
