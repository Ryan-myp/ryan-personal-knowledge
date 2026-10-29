"""One content revision for the workspace loader and all of its dependencies."""

import hashlib
from pathlib import Path

from starlette.responses import HTMLResponse, Response
from starlette.staticfiles import StaticFiles


VERSION_MARKER = "__WORKSPACE_ASSET_VERSION__"


class WorkspaceAssets(StaticFiles):
    def __init__(self, directory: Path):
        super().__init__(directory=directory)
        digest = hashlib.sha256()
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix in {".js", ".css"}:
                digest.update(path.relative_to(directory).as_posix().encode() + b"\0")
                digest.update(hashlib.sha256(path.read_bytes()).digest())
        # Compute once at process startup, not on each page or module request.
        self.version = digest.hexdigest()[:24]
        self.stylesheet = self._render(directory / "css/chat.css")

    def _render(self, path: Path) -> str:
        return path.read_text(encoding="utf-8").replace(VERSION_MARKER, self.version)

    def page(self, template: Path) -> HTMLResponse:
        return HTMLResponse(self._render(template), headers={"Cache-Control": "no-store"})

    async def get_response(self, path, scope):
        if path == "css/chat.css" and scope["method"] in {"GET", "HEAD"}:
            return Response(
                self.stylesheet if scope["method"] == "GET" else "",
                media_type="text/css", headers={
                    "Cache-Control": "no-cache",
                    "Content-Length": str(len(self.stylesheet.encode("utf-8"))),
                },
            )
        response = await super().get_response(path, scope)
        # Preserve ETag/304 support while requiring validation for reused URLs.
        response.headers["Cache-Control"] = "no-cache"
        return response
