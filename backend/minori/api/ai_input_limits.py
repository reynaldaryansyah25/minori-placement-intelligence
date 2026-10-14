"""Bound AI request streams, including chunked uploads without Content-Length."""

from fastapi import HTTPException
from starlette.responses import JSONResponse


class AiInputLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        protected = path.startswith("/ai/") or "/email/" in path
        if scope["type"] != "http" or not protected:
            return await self.app(scope, receive, send)
        limit = 6 * 1024 * 1024 if path == "/ai/documents/preview" else 512 * 1024
        length = dict(scope.get("headers", [])).get(b"content-length", b"0")
        if not length.isdigit() or int(length) > limit:
            return await JSONResponse(
                status_code=413, content={"detail": "Dokumen melebihi batas ukuran aman."}
            )(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(status_code=413, detail="Dokumen melebihi batas ukuran aman.")
            return message

        return await self.app(scope, bounded_receive, send)
