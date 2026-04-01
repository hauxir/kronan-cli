import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from kronan_cli.client import COGNITO_CLIENT_ID, COGNITO_DOMAIN, COGNITO_REGION

# Cognito OAuth2 endpoints
COGNITO_TOKEN_URL = f"https://{COGNITO_DOMAIN}/oauth2/token"
COGNITO_AUTHORIZE_URL = f"https://{COGNITO_DOMAIN}/oauth2/authorize"

AUTH_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Kronan CLI - Login</title>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #f5f5f5; color: #333;
               display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { background: #fff; border-radius: 12px; padding: 2rem; max-width: 400px; width: 90%;
                     text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #d4001a; }
        .status { margin-top: 1rem; padding: 0.7rem; border-radius: 8px; font-size: 0.9rem; }
        .success { background: #d4edda; color: #155724; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Kronan CLI</h1>
        <div class="status success">Login successful! You can close this window.</div>
    </div>
</body>
</html>"""


def run_auth_server(port: int = 8421) -> dict[str, Any] | None:
    """Start local server, open Cognito OAuth login in browser, capture tokens."""
    result: dict[str, Any] | None = None
    server_ready = threading.Event()
    got_token = threading.Event()
    redirect_uri = f"http://localhost:{port}/callback"

    class AuthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            nonlocal result
            parsed = urlparse(self.path)

            if parsed.path == "/callback":
                params = parse_qs(parsed.query)
                code = params.get("code", [None])[0]
                error = params.get("error", [None])[0]

                if error:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())
                    got_token.set()
                    return

                if code:
                    # Exchange authorization code for tokens
                    try:
                        with httpx.Client(timeout=30.0) as http:
                            resp = http.post(
                                COGNITO_TOKEN_URL,
                                data={
                                    "grant_type": "authorization_code",
                                    "client_id": COGNITO_CLIENT_ID,
                                    "code": code,
                                    "redirect_uri": redirect_uri,
                                },
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                            )
                            resp.raise_for_status()
                            tokens = resp.json()
                            result = {
                                "id_token": tokens.get("id_token", ""),
                                "access_token": tokens.get("access_token", ""),
                                "refresh_token": tokens.get("refresh_token", ""),
                            }
                    except Exception as e:
                        result = {"error": str(e)}

                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(AUTH_HTML.encode())
                    got_token.set()
                    return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("localhost", port), AuthHandler)
    server.timeout = 300

    def serve() -> None:
        server_ready.set()
        while not got_token.is_set():
            server.handle_request()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server_ready.wait()

    # Build Cognito authorize URL
    auth_url = (
        f"{COGNITO_AUTHORIZE_URL}"
        f"?client_id={COGNITO_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=openid+profile"
        f"&redirect_uri={redirect_uri}"
    )
    webbrowser.open(auth_url)

    got_token.wait(timeout=300)
    server.server_close()

    return result
