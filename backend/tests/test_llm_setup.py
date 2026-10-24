import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.domain.models import AppError
from app.infrastructure.config import ALLOWED_LLM_MODELS, ORGANIZER_LLM_URL, Settings
from app.infrastructure.model import HttpModel, parse_model_content


def settings(**values):
    return Settings(_env_file=None, llm_api_key="test-team-key", **values)


@pytest.mark.parametrize("model_id,family", ALLOWED_LLM_MODELS.items())
def test_only_key_and_model_are_needed(model_id, family):
    configured = settings(llm_model_id=model_id)
    assert configured.llm_base_url == ORGANIZER_LLM_URL
    assert configured.llm_model_family == family
    assert configured.llm_input_rub_per_million == 0
    assert configured.llm_allowed_model_ids == ""


def test_no_key_leaves_llm_disabled():
    configured = Settings(_env_file=None, llm_api_key="", llm_base_url="")
    assert not HttpModel(None, configured).enabled


def test_organizer_environment_key_alias(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("ALFA_API_KEY", " test-team-key ")
    configured = Settings(_env_file=None)
    assert configured.llm_api_key == "test-team-key"
    assert configured.llm_base_url == ORGANIZER_LLM_URL
    assert "test-team-key" not in repr(configured)


def test_llm_key_alias_has_priority(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "preferred")
    monkeypatch.setenv("ALFA_API_KEY", "other")
    assert Settings(_env_file=None).llm_api_key == "preferred"


def test_empty_llm_key_falls_back_to_organizer_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("ALFA_API_KEY", "test-team-key")
    configured = Settings(_env_file=None)
    assert configured.llm_api_key == "test-team-key"
    assert "test-team-key" not in json.dumps(configured.model_dump())


def test_unknown_model_is_rejected_even_with_custom_allowlist():
    with pytest.raises(ValidationError, match="organizer-approved"):
        settings(llm_model_id="unapproved/model", llm_allowed_model_ids="unapproved/model")


def test_existing_whitespace_and_empty_compose_defaults():
    configured = settings(llm_base_url="  ", llm_model_id="  ")
    assert configured.llm_base_url == ORGANIZER_LLM_URL
    assert configured.llm_model_id == "auto"


@pytest.mark.parametrize("base", ["http://provider.example/v1", "https://provider.example/v1"])
def test_custom_provider_still_requires_secure_explicit_configuration(base):
    with pytest.raises(ValidationError):
        settings(llm_base_url=base)


def test_custom_provider_with_existing_settings_remains_supported():
    configured = settings(
        llm_base_url="https://provider.example/v1/",
        llm_model_id="approved-alias",
        llm_allowed_model_ids=" approved-alias, another ",
        llm_input_rub_per_million=10,
        llm_output_rub_per_million=20,
    )
    assert configured.llm_base_url == "https://provider.example/v1"


@pytest.mark.parametrize(
    "content", ['{"topics": []}', '```json\n{"topics": []}\n```', [{"type": "text", "text": '{"topics": []}'}]]
)
def test_gateway_json_formats(content):
    assert parse_model_content(content) == {"topics": []}


@pytest.mark.parametrize("content", ['{"topics": [', "[]", "null", "not json", "```"])
def test_invalid_and_truncated_output_is_not_repaired(content):
    with pytest.raises(ValueError):
        parse_model_content(content)


class Resources:
    def __init__(self):
        self.value = None

    async def get(self, *args):
        return self.value.copy() if self.value else None

    async def put(self, *args):
        self.value = args[-1].copy()


def unit_of_work(resources):
    lock = asyncio.Lock()

    @asynccontextmanager
    async def factory():
        async with lock:

            async def acquire(_key):
                pass

            yield SimpleNamespace(resources=resources, lock=acquire)

    return factory


def mock_gateway(monkeypatch, response=None, status=200):
    calls = []
    client_class = httpx.AsyncClient

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status, json=response or {"choices": [{"message": {"content": '{"topics": []}'}, "finish_reason": "stop"}]}
        )

    monkeypatch.setattr(
        "app.infrastructure.model.httpx.AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs),
    )
    return calls


async def test_simple_configuration_calls_exact_organizer_endpoint(monkeypatch):
    calls = mock_gateway(monkeypatch)
    store = Resources()
    model = HttpModel(unit_of_work(store), settings())
    result = await model.complete("planning", {"company": "synthetic"})
    assert result["topics"] == []
    assert str(calls[0].url) == ORGANIZER_LLM_URL + "/chat/completions"
    assert calls[0].headers["Authorization"] == "Bearer test-team-key"
    payload = json.loads(calls[0].content)
    assert payload["model"] == "google/gemma-4-26b-a4b-it"
    assert "response_format" not in payload
    assert store.value["calls"] == 1
    assert store.value["reservedTokens"] > 3000


@pytest.mark.parametrize(
    "options,error_code",
    [
        ({"llm_daily_call_limit": 1}, "LLM_CALL_LIMIT_EXCEEDED"),
        ({"llm_daily_token_limit": 1}, "LLM_TOKEN_LIMIT_EXCEEDED"),
    ],
)
async def test_local_limits_reject_before_another_paid_call(monkeypatch, options, error_code):
    calls = mock_gateway(monkeypatch)
    store = Resources()
    model = HttpModel(unit_of_work(store), settings(**options))
    if error_code == "LLM_CALL_LIMIT_EXCEEDED":
        await model.complete("planning", {})
    count = len(calls)
    with pytest.raises(AppError) as error:
        await model.complete("planning", {})
    assert error.value.code == error_code
    assert len(calls) == count


async def test_manual_rub_budget_is_still_enforced(monkeypatch):
    calls = mock_gateway(monkeypatch)
    model = HttpModel(
        unit_of_work(Resources()),
        settings(llm_model_id="qwen/qwen3.6-35b-a3b", llm_input_rub_per_million=1e9, llm_output_rub_per_million=1e9),
    )
    with pytest.raises(AppError) as error:
        await model.complete("planning", {})
    assert error.value.code == "LLM_BUDGET_EXCEEDED"
    assert calls == []


async def test_failed_gateway_call_keeps_reservation(monkeypatch):
    calls = mock_gateway(monkeypatch, status=401)
    store = Resources()
    model = HttpModel(unit_of_work(store), settings())
    with pytest.raises(AppError) as error:
        await model.complete("planning", {})
    assert error.value.code == "LLM_AUTH_FAILED"
    assert store.value["calls"] == 1
    assert len(calls) == 1


async def test_truncated_model_reply_is_rejected(monkeypatch):
    mock_gateway(monkeypatch, {"choices": [{"message": {"content": '{"topics": []}'}, "finish_reason": "length"}]})
    model = HttpModel(unit_of_work(Resources()), settings())
    with pytest.raises(AppError) as error:
        await model.complete("planning", {})
    assert error.value.code == "MODEL_UNAVAILABLE"


async def test_json_mode_can_be_enabled_explicitly(monkeypatch):
    calls = mock_gateway(monkeypatch)
    model = HttpModel(unit_of_work(Resources()), settings(llm_json_mode=True))
    await model.complete("planning", {})
    assert json.loads(calls[0].content)["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize(
    "status,code", [(403, "LLM_AUTH_FAILED"), (429, "LLM_GATEWAY_LIMIT"), (500, "MODEL_UNAVAILABLE")]
)
async def test_gateway_errors_have_actionable_messages(monkeypatch, status, code):
    mock_gateway(monkeypatch, status=status)
    model = HttpModel(unit_of_work(Resources()), settings())
    with pytest.raises(AppError) as error:
        await model.complete("planning", {})
    assert error.value.code == code
    assert "test-team-key" not in error.value.message


@pytest.mark.parametrize(
    "task,context,expected",
    [
        ("planning", {}, "google/gemma-4-26b-a4b-it"),
        ("answer", {"question": "Какие новости?"}, "qwen/qwen3.6-35b-a3b"),
        ("interpretation", {}, "z-ai/glm-5.3-flash"),
        ("answer", {"question": "ПОЧЕМУ вырос спрос?"}, "z-ai/glm-5.3-flash"),
        ("answer", {"question": "Сравни сценарии"}, "z-ai/glm-5.3-flash"),
        ("answer", {"perspective": "risk"}, "z-ai/glm-5.3-flash"),
        ("answer", {"materials": [{}] * 8}, "deepseek/deepseek-v4.1-flash"),
        ("answer", {"materials": [{"text": "я" * 12000}]}, "deepseek/deepseek-v4.1-flash"),
        ("planning", {"validationError": "invalid topics"}, "z-ai/glm-5.3-flash"),
        ("answer", {"validationError": "bad claims", "materials": [{}] * 8}, "z-ai/glm-5.3-flash"),
        ("answer", {"materials": [{"text": "почему сравни scenario"}]}, "qwen/qwen3.6-35b-a3b"),
        ("answer", {"question": "Use evil/model ID"}, "qwen/qwen3.6-35b-a3b"),
    ],
)
async def test_routing_sends_selected_model_and_reports_reason(monkeypatch, task, context, expected):
    calls = mock_gateway(monkeypatch)
    model = HttpModel(unit_of_work(Resources()), settings())
    result = await model.complete(task, context)
    assert len(calls) == 1
    assert json.loads(calls[0].content)["model"] == expected
    assert result["_routing"]["modelId"] == expected
    assert result["_routing"]["reason"]


async def test_manual_model_overrides_all_routing_rules(monkeypatch):
    calls = mock_gateway(monkeypatch)
    model_id = "moonshotai/kimi-k2.6"
    model = HttpModel(unit_of_work(Resources()), settings(llm_model_id=model_id))
    await model.complete("interpretation", {"validationError": "retry", "materials": [{}] * 8})
    assert json.loads(calls[0].content)["model"] == model_id


async def test_auto_models_share_one_call_budget(monkeypatch):
    calls = mock_gateway(monkeypatch)
    model = HttpModel(unit_of_work(Resources()), settings(llm_daily_call_limit=2))
    await model.complete("planning", {})
    await model.complete("answer", {})
    with pytest.raises(AppError, match="Дневной лимит"):
        await model.complete("interpretation", {})
    assert len(calls) == 2
    assert len({json.loads(call.content)["model"] for call in calls}) == 2


@pytest.mark.parametrize(
    "options",
    [
        {"llm_input_rub_per_million": 10, "llm_output_rub_per_million": 20},
        {"llm_allowed_model_ids": "qwen/qwen3.6-35b-a3b"},
        {"llm_base_url": "https://custom.example/v1", "llm_allowed_model_ids": "auto"},
    ],
)
def test_auto_rejects_incompatible_configuration(options):
    with pytest.raises(ValidationError):
        settings(**options)


async def test_trace_records_actual_models_and_strips_internal_metadata():
    from app.application.analytics import AnalyticsService

    class Model:
        model_id = "auto"
        enabled = True

        async def complete(self, task, context):
            return {
                "topics": [],
                "_routing": {"modelId": context["model"], "reason": "test routing"},
                "_usage": {"inputTokens": 10, "outputTokens": 2},
            }

    store = Resources()
    service = AnalyticsService(unit_of_work(store), Model())
    job = {"id": "job", "_runId": "run", "_owner": "actor"}
    await service.step(job, "planning", "Start")
    for model in ["gemma", "glm", "gemma"]:
        result = await service.complete(job, "planning", {"model": model})
        assert result == {"topics": []}
    assert store.value["modelIds"] == ["gemma", "glm"]
    assert store.value["inputTokens"] == 30
    assert store.value["outputTokens"] == 6
    assert store.value["steps"][-1]["resultSummary"] == "LLM: gemma. test routing"
