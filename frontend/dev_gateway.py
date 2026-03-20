from __future__ import annotations

import asyncio
import mimetypes
import os
import subprocess
from pathlib import Path
from typing import Optional

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web


BASE_DIR = Path(__file__).resolve().parent
BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://127.0.0.1:5000").rstrip("/")
HOST = os.environ.get("DEV_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("DEV_GATEWAY_PORT", "10088"))
TIMEOUT = ClientTimeout(total=600)


async def serve_static(request: web.Request) -> web.StreamResponse:
    relative_path = request.match_info.get("path", "").strip("/")
    if not relative_path:
        relative_path = "index.html"
    file_path = BASE_DIR / relative_path
    if not file_path.exists() or file_path.is_dir():
        file_path = BASE_DIR / "index.html"
    content_type, _ = mimetypes.guess_type(str(file_path))
    return web.FileResponse(path=file_path, headers={"Content-Type": content_type or "text/html; charset=utf-8"})


def resolve_kongkong_target(slug: str) -> Optional[str]:
    container_name = f"kongkong-{slug}"
    result = subprocess.run(
        ["docker", "port", container_name, "18789/tcp"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip().splitlines()[0].strip()
    if not value:
        return None
    host, _, port = value.rpartition(":")
    if not port:
        return None
    host = host or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"http://{host}:{port}"


async def proxy_api(request: web.Request) -> web.StreamResponse:
    target = f"{BACKEND_BASE}{request.path_qs}"
    body = await request.read()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    async with ClientSession(timeout=TIMEOUT) as session:
        async with session.request(request.method, target, headers=headers, data=body) as response:
            payload = await response.read()
            proxy_response = web.Response(body=payload, status=response.status)
            for key, value in response.headers.items():
                if key.lower() in {"content-length", "transfer-encoding", "connection", "content-encoding"}:
                    continue
                proxy_response.headers[key] = value
            return proxy_response


async def proxy_kongkong(request: web.Request) -> web.StreamResponse:
    slug = request.match_info["slug"]
    remainder = request.match_info.get("tail", "")
    if request.path == f"/kongkong/{slug}/" and request.query.get("gateway_bootstrapped") != "1":
        raise web.HTTPFound(location=f"/kongkong-launch.html?slug={slug}")

    target_base = resolve_kongkong_target(slug)
    if not target_base:
        raise web.HTTPBadGateway(text="KongKong runtime unavailable")

    target_path = "/"
    if remainder:
        target_path = "/" + remainder
    if request.path == f"/kongkong/{slug}":
        target_path = "/"

    target = f"{target_base}{target_path}"
    if request.query_string:
        target += f"?{request.query_string}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    headers["X-Forwarded-Prefix"] = f"/kongkong/{slug}"

    is_websocket = request.headers.get("Upgrade", "").lower() == "websocket"
    if is_websocket:
        client_ws = web.WebSocketResponse()
        await client_ws.prepare(request)
        async with ClientSession(timeout=TIMEOUT) as session:
            async with session.ws_connect(
                target.replace("http://", "ws://").replace("https://", "wss://"),
                headers=headers,
            ) as upstream_ws:
                async def forward_client_to_upstream():
                    async for message in client_ws:
                        if message.type == WSMsgType.TEXT:
                            await upstream_ws.send_str(message.data)
                        elif message.type == WSMsgType.BINARY:
                            await upstream_ws.send_bytes(message.data)
                        elif message.type == WSMsgType.CLOSE:
                            await upstream_ws.close()

                async def forward_upstream_to_client():
                    async for message in upstream_ws:
                        if message.type == WSMsgType.TEXT:
                            await client_ws.send_str(message.data)
                        elif message.type == WSMsgType.BINARY:
                            await client_ws.send_bytes(message.data)
                        elif message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED):
                            await client_ws.close()

                await asyncio.gather(forward_client_to_upstream(), forward_upstream_to_client())
        return client_ws

    body = await request.read()
    async with ClientSession(timeout=TIMEOUT) as session:
        async with session.request(request.method, target, headers=headers, data=body) as response:
            payload = await response.read()
            proxy_response = web.Response(body=payload, status=response.status)
            for key, value in response.headers.items():
                if key.lower() in {"content-length", "transfer-encoding", "connection", "content-encoding"}:
                    continue
                proxy_response.headers[key] = value
            return proxy_response


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_route("*", "/api/{tail:.*}", proxy_api)
    app.router.add_route("*", "/kongkong/{slug}", proxy_kongkong)
    app.router.add_route("*", "/kongkong/{slug}/", proxy_kongkong)
    app.router.add_route("*", "/kongkong/{slug}/{tail:.*}", proxy_kongkong)
    app.router.add_get("/{path:.*}", serve_static)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host=HOST, port=PORT)
