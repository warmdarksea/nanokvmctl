"""NanoKVM client extended with the HTTP image-upload endpoint.

The `nanokvm` library covers power/media/mount, but not `POST /api/download/file`
(the multipart image upload). We add it here, reusing the authenticated session.

Server-side rules (from the NanoKVM `DownloadImageFile` handler): the multipart
field must be named `file`, the filename must match `^[A-Za-z0-9._-]+$` and end in
`.iso`, and the file is stored at `/data/<filename>`.
"""

from __future__ import annotations

import os
import re

import aiohttp

try:
    from nanokvm.client import NanoKVMClient
except ImportError:  # pragma: no cover
    from nanokvm import NanoKVMClient  # type: ignore

_VALID_NAME = re.compile(r"^[a-zA-Z0-9._-]+$")


def sanitize_iso_name(name: str) -> str:
    """Turn any local filename into one the NanoKVM accepts: [A-Za-z0-9._-] + .iso."""
    base = os.path.basename(name)
    stem = re.sub(r"\.(img|iso|bin|raw)$", "", base, flags=re.IGNORECASE)
    stem = re.sub(r"[^a-zA-Z0-9._-]", "_", stem)
    return (stem or "image") + ".iso"


class NanoKVMCtlClient(NanoKVMClient):
    async def _json(self, method: str, path: str, **kwargs):
        async with self._request(method, path, **kwargs) as resp:
            return await resp.json(content_type=None)

    async def image_upload_enabled(self) -> bool:
        data = (await self._json("GET", "download/image/enabled")) or {}
        return bool(data.get("data", {}).get("enabled"))

    async def download_status(self) -> dict:
        data = (await self._json("GET", "download/image/status")) or {}
        return data.get("data", {})

    async def upload_image(self, local_path: str, name: str | None = None) -> str:
        """Upload a local image to the NanoKVM's /data over HTTP.

        Returns the on-device path (``/data/<name>``) to hand to mount.
        """
        name = sanitize_iso_name(name or local_path)
        if not _VALID_NAME.match(name):
            raise ValueError(f"invalid upload name: {name!r}")

        form = aiohttp.FormData()
        with open(local_path, "rb") as fh:
            form.add_field("file", fh, filename=name, content_type="application/octet-stream")
            # The client's request_timeout governs this; set it high for big images.
            async with self._request("POST", "download/file", data=form) as resp:
                result = await resp.json(content_type=None)

        if not result or result.get("code") != 0:
            raise RuntimeError(f"upload failed: {(result or {}).get('msg', 'unknown error')}")
        return f"/data/{name}"
