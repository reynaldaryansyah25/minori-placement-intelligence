"""Fail-closed sandbox request isolation and quotas before parsing or business operations."""

import json
import secrets

from starlette.responses import JSONResponse

from minori.integrations.demo_sandbox import SandboxDenied


class SandboxBoundaryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        application = scope["app"]
        settings = application.state.settings
        if not settings.sandbox_enabled:
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"]
        if path == "/health" or path == "/sandbox/sessions":
            return await self.app(scope, receive, send)
        manager = application.state.sandbox
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        worker = secrets.compare_digest(
            token.encode(), settings.sandbox_worker_token.get_secret_value().encode()
        )
        row = None
        try:
            if worker:
                if path == "/sandbox/worker/sessions" and method == "GET":
                    return await self.app(scope, receive, send)
                if not path.startswith("/internal/reminders/") and not (
                    settings.app_env == "test" and path == "/internal/demo/clock"
                ):
                    raise SandboxDenied(403, "Worker hanya dapat memproses antrean sandbox.")
                row = manager.worker_session(
                    headers.get(b"x-sandbox-session", b"").decode(),
                    callback=path.endswith(("/complete", "/fail")),
                )
            else:
                row = manager.authenticate(token)
                if path.startswith(("/internal/", "/sandbox/worker/")):
                    raise SandboxDenied(403, "Akses internal tidak tersedia bagi peserta demo.")
            scope.setdefault("state", {})["sandbox_session"] = row
            scope["state"]["sandbox_worker"] = worker
            # Entire request body is bounded, including requests without Content-Length.
            body = bytearray()
            limit = 2 * 1024 * 1024 + 65536 if path == "/ai/documents/preview" else 512 * 1024
            length = headers.get(b"content-length", b"0")
            if not length.isdigit() or int(length) > limit:
                raise SandboxDenied(413, "Ukuran unggahan sandbox maksimal 2 MB.")
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    raise SandboxDenied(413, "Ukuran unggahan sandbox maksimal 2 MB.")
                if not message.get("more_body", False):
                    break
            payload = {}
            if headers.get(b"content-type", b"").startswith(b"application/json") and body:
                try:
                    payload = json.loads(body)
                except (ValueError, UnicodeError):
                    raise SandboxDenied(422, "Format masukan tidak valid.") from None
                if not isinstance(payload, dict):
                    raise SandboxDenied(422, "Format masukan tidak valid.")
                if not worker and "actor_reference" in payload:
                    payload["actor_reference"] = "demo." + row.identifier[:12]
                    body = bytearray(json.dumps(payload).encode())
                if (
                    path.startswith("/candidates")
                    and payload.get("email")
                    and not str(payload["email"]).endswith(".invalid")
                ):
                    raise SandboxDenied(
                        422, "Gunakan alamat sintetis dengan domain .invalid di sandbox."
                    )
            if (
                not worker
                and method not in {"GET", "HEAD"}
                and path not in {"/sandbox/logout", "/sandbox/reset"}
            ):
                manager.consume(row, "writes")
                if path == "/ai/documents/preview":
                    manager.consume(row, "uploads")
                if path in {
                    "/ai/vacancies/analyze",
                    "/ai/vacancies/batch",
                    "/ai/matching/explanation",
                } or path.endswith("/email/draft"):
                    amount = len(payload.get("texts", [])) if path.endswith("/batch") else 1
                    if not 1 <= amount <= 5:
                        raise SandboxDenied(422, "Pilih satu sampai lima lowongan.")
                    manager.consume(row, "ai", amount)
                if path.endswith("/email/approve"):
                    # A repeated approval consumes no additional email budget; the service
                    # separately validates snapshot and idempotency before enqueueing.
                    identifier = path.split("/")[2]
                    manager.consume(row, "emails", key=manager.email_key(row, identifier))
            control = path in {"/sandbox/reset", "/sandbox/logout"}
            if not control:
                manager.begin(row, touch=not worker)
            consumed = False

            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": bytes(body)}
                return await receive()

            try:
                return await self.app(scope, replay, send)
            finally:
                if not control:
                    manager.finish(row)
        except SandboxDenied as error:
            return await JSONResponse(status_code=error.status, content={"detail": error.message})(
                scope, receive, send
            )
