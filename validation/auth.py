"""Shared auth-token helper for validation checks that hit protected modular-api routes.

Registers (or logs into, if already registered) a dedicated validation
service-account user and caches the resulting Bearer token for the
lifetime of the process so every check in a single `python -m
validation.runner` run reuses one token instead of re-authenticating.
"""

import json
import urllib.error
import urllib.request

_token_cache: dict[str, str | None] = {}


def get_auth_token(config) -> str | None:
    """Return a cached Bearer token for the validation user, or None if auth is unreachable."""
    if "token" in _token_cache:
        return _token_cache["token"]

    token = _register_or_login(config)
    _token_cache["token"] = token
    return token


def get_auth_headers(config) -> dict[str, str]:
    """Return an Authorization header dict, or {} if a token could not be obtained."""
    token = get_auth_token(config)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def _register_or_login(config) -> str | None:
    base = config.modular_api_url
    email = config.validation_user_email
    username = config.validation_user_username
    password = config.validation_user_password

    status, body = _post_json(
        f"{base}/auth/register",
        {"email": email, "username": username, "password": password},
        config.http_timeout,
    )
    if status == 201 and body.get("access_token"):
        return body["access_token"]

    # Already exists (409) or register endpoint rejected it for another reason -> try login.
    status, body = _post_json(
        f"{base}/auth/login",
        {"email": email, "password": password},
        config.http_timeout,
    )
    if status == 200 and body.get("access_token"):
        return body["access_token"]
    return None
