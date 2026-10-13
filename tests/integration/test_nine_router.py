"""Validate OpenAI-compatible requests against a local synthetic HTTP server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from minori.core.config import Settings
from minori.domain.ports import ChatMessage
from minori.integrations.nine_router.client import NineRouterClient, RouterConfigurationError


@pytest.fixture
def synthetic_router():
    requests = []
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
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                }
            )
            payload = json.dumps(response).encode()
            self.send_response(200)
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
        yield settings, requests, response
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_router_sends_configured_key_model_and_endpoint(synthetic_router):
    settings, requests, _ = synthetic_router
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
                },
            }
        ]
    finally:
        router.close()


def test_disabled_router_is_never_created(settings):
    with pytest.raises(RouterConfigurationError, match="Enable"):
        NineRouterClient(settings)


def test_router_rejects_empty_input_without_request(synthetic_router):
    settings, requests, _ = synthetic_router
    router = NineRouterClient(settings)
    try:
        with pytest.raises(ValueError, match="At least one"):
            router.complete([])
        assert requests == []
    finally:
        router.close()


def test_router_reports_missing_response_text(synthetic_router):
    settings, _, response = synthetic_router
    response["choices"][0]["message"]["content"] = None
    router = NineRouterClient(settings)
    try:
        with pytest.raises(ValueError, match="no text"):
            router.complete([ChatMessage(role="user", content="Synthetic input")])
    finally:
        router.close()
