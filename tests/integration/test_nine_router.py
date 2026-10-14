"""Validate OpenAI-compatible requests against a local synthetic HTTP server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from minori.core.config import Settings
from minori.domain.ports import ChatMessage
from minori.integrations.nine_router.client import NineRouterClient, RouterConfigurationError
from openai import APIStatusError, OpenAI


@pytest.fixture
def synthetic_router():
    requests = []
    behavior = {}
    response = {
        "id": "synthetic-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "synthetic-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Synthetic response"},
                "finish_reason": "stop",
            }
        ],
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": body,
                }
            )
            status, data = behavior.get(body["model"], (200, response))
            payload = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *args):
            """Keep synthetic credentials out of HTTP server logs."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = Settings(
        _env_file=None,
        llm_enabled=True,
        nine_router_base_url=f"http://127.0.0.1:{server.server_port}/v1",
        nine_router_api_key="synthetic-key",
        nine_router_model="synthetic-model",
        llm_timeout_seconds=5,
        llm_max_retries=0,
    )
    try:
        yield settings, requests, response, behavior
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_router_sends_configured_key_model_and_endpoint(synthetic_router):
    settings, requests, _, _ = synthetic_router
    router = NineRouterClient(settings)
    try:
        assert requests == []
        result = router.complete([ChatMessage(role="user", content="Synthetic input")])
        assert result == "Synthetic response"
        assert requests == [
            {
                "path": "/v1/chat/completions",
                "authorization": "Bearer synthetic-key",
                "body": {
                    "model": "synthetic-model",
                    "messages": [{"role": "user", "content": "Synthetic input"}],
                    "stream": False,
                },
            }
        ]
    finally:
        router.close()


def test_disabled_router_is_never_created(settings):
    with pytest.raises(RouterConfigurationError, match="Enable"):
        NineRouterClient(settings)


@pytest.mark.parametrize("failure", [httpx.ReadTimeout, httpx.ConnectError])
def test_transport_failures_use_next_model(synthetic_router, failure):
    settings, _, response, _ = synthetic_router
    settings = settings.model_copy(update={"nine_router_fallback_models": "backup-one"})
    requests = []

    def handle(request):
        model = json.loads(request.content)["model"]
        requests.append(model)
        if model == "synthetic-model":
            raise failure("Synthetic failure", request=request)
        return httpx.Response(200, json=response)

    router = NineRouterClient(settings)
    router._client.close()
    router._client = OpenAI(
        base_url=str(settings.nine_router_base_url),
        api_key="synthetic-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    try:
        assert router.complete([ChatMessage(role="user", content="Synthetic input")])
        assert requests == ["synthetic-model", "backup-one"]
        assert router.last_model == "backup-one"
    finally:
        router.close()


def test_expired_budget_prevents_further_model_calls(synthetic_router, monkeypatch):
    settings, requests, _, behavior = synthetic_router
    settings = settings.model_copy(update={"nine_router_fallback_models": "backup-one,backup-two"})
    behavior["synthetic-model"] = (503, {"error": {"message": "Unavailable"}})
    ticks = iter((0, 0, settings.llm_timeout_seconds + 1))
    monkeypatch.setattr("minori.integrations.nine_router.client.monotonic", lambda: next(ticks))
    router = NineRouterClient(settings)
    try:
        with pytest.raises(APIStatusError):
            router.complete([ChatMessage(role="user", content="Synthetic input")])
        assert len(requests) == 1
    finally:
        router.close()


def test_invalid_model_output_still_requires_structured_validation(synthetic_router):
    from minori.domain.ai import AiOutputError
    from minori.integrations.nine_router.structured import ValidatedAiGateway

    settings, requests, _, _ = synthetic_router
    settings = settings.model_copy(update={"nine_router_fallback_models": "backup-one"})
    router = NineRouterClient(settings)
    try:
        with pytest.raises(AiOutputError):
            ValidatedAiGateway(router).generate("matching", {"official": {}})
        # A fallback cannot bypass the output contract or retry arbitrary invalid output.
        assert len(requests) == 1
    finally:
        router.close()


def test_router_rejects_empty_input_without_request(synthetic_router):
    settings, requests, _, _ = synthetic_router
    router = NineRouterClient(settings)
    try:
        with pytest.raises(ValueError, match="At least one"):
            router.complete([])
        assert requests == []
    finally:
        router.close()


def test_router_reports_missing_response_text(synthetic_router):
    settings, _, response, _ = synthetic_router
    response["choices"][0]["message"]["content"] = None
    router = NineRouterClient(settings)
    try:
        with pytest.raises(ValueError, match="no text"):
            router.complete([ChatMessage(role="user", content="Synthetic input")])
    finally:
        router.close()


def test_quota_and_provider_failure_fall_back_in_order(synthetic_router, caplog):
    settings, requests, _, behavior = synthetic_router
    settings = settings.model_copy(
        update={"nine_router_fallback_models": "backup-one,backup-two", "llm_max_retries": 5}
    )
    # A gateway can wrap the provider's quota error inside HTTP 503.
    for model, status in (("synthetic-model", 429), ("backup-one", 503)):
        behavior[model] = (status, {"error": {"message": "synthetic-private-key private input"}})
    router = NineRouterClient(settings)
    try:
        assert router.complete([ChatMessage(role="user", content="private input")])
        assert [r["body"]["model"] for r in requests] == [
            "synthetic-model",
            "backup-one",
            "backup-two",
        ]
        assert all(r["body"]["stream"] is False for r in requests)
        assert router.last_model == "backup-two"
        assert "synthetic-private-key" not in caplog.text
        assert "private input" not in caplog.text
    finally:
        router.close()


@pytest.mark.parametrize("status", [400, 401, 403, 422])
def test_authentication_and_invalid_requests_do_not_try_other_models(synthetic_router, status):
    settings, requests, _, behavior = synthetic_router
    settings = settings.model_copy(update={"nine_router_fallback_models": "backup-one"})
    behavior["synthetic-model"] = (status, {"error": {"message": "Rejected"}})
    router = NineRouterClient(settings)
    try:
        with pytest.raises(APIStatusError) as error:
            router.complete([ChatMessage(role="user", content="Synthetic input")])
        assert error.value.status_code == status
        assert len(requests) == 1
        assert router.last_model is None
    finally:
        router.close()


def test_all_models_unavailable_have_bounded_attempts(synthetic_router):
    settings, requests, _, behavior = synthetic_router
    settings = settings.model_copy(
        update={"nine_router_fallback_models": "backup-one,backup-two", "llm_max_retries": 5}
    )
    for model in ("synthetic-model", "backup-one", "backup-two"):
        behavior[model] = (503, {"error": {"message": "Unavailable"}})
    router = NineRouterClient(settings)
    try:
        with pytest.raises(APIStatusError):
            router.complete([ChatMessage(role="user", content="Synthetic input")])
        assert len(requests) == 3
        assert router.last_model is None
    finally:
        router.close()


def test_primary_success_does_not_call_fallback_or_change_messages(synthetic_router):
    settings, requests, _, _ = synthetic_router
    settings = settings.model_copy(
        update={"nine_router_fallback_models": "synthetic-model,backup-one"}
    )
    router = NineRouterClient(settings)
    try:
        router.complete(
            [ChatMessage(role="system", content="Rules"), ChatMessage(role="user", content="Data")]
        )
        assert len(requests) == 1
        assert requests[0]["body"]["messages"] == [
            {"role": "system", "content": "Rules"},
            {"role": "user", "content": "Data"},
        ]
        assert router.last_model == "synthetic-model"
    finally:
        router.close()
