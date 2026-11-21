"""Test-only HTTP transport using the same Uvicorn runtime as NeuroAccess."""

from contextlib import contextmanager
from dataclasses import dataclass
from http.cookiejar import CookieJar
import json as json_codec
import socket
from threading import Thread
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

import uvicorn


@contextmanager
def serve(app):
    """Serve the temporary test app on an OS-assigned loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            app, http="h11", ws="none", lifespan="on", log_level="error",
            access_log=False, timeout_graceful_shutdown=2,
        ))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 10
            while not server.started:
                if not thread.is_alive():
                    raise RuntimeError("Isolated BBC-BE test server exited during startup.")
                if monotonic() >= deadline:
                    raise TimeoutError("Isolated BBC-BE test server did not start within 10 seconds.")
                sleep(0.01)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("Isolated BBC-BE test server did not stop within 5 seconds.")


@dataclass(frozen=True)
class Response:
    status_code: int
    text: str

    def json(self):
        return json_codec.loads(self.text)


class LocalClient:
    """Separate client instances have separate cookies, including anonymous requests."""

    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {}
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))

    def request(self, method, path, *, params=None, headers=None, json=None):
        url = self.base_url + path
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params)
        request_headers = {**self.headers, **(headers or {})}
        data = None
        if json is not None:
            data = json_codec.dumps(json).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return Response(response.code, response.read().decode("utf-8"))

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)
