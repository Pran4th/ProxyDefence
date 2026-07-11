"""Robust JSON decoding for third-party news APIs.

GNews and NewsData.io occasionally emit Windows-1252 smart punctuation
(curly quotes, en/em dashes) inside a response body that is otherwise
UTF-8 and labeled as such. ``requests``' default decode path
(``Response.json()`` / ``Response.text``) decodes strictly as UTF-8 with
``errors="replace"``, which silently turns each offending byte into an
unrecoverable U+FFFD replacement character before it ever reaches our
pipeline. Registering a targeted error handler lets us fall back to
CP-1252 only for the exact invalid byte(s), leaving the surrounding
(valid) UTF-8 text untouched.
"""

import codecs
import json

import requests


def _cp1252_fallback(error: UnicodeDecodeError):
    chunk = error.object[error.start:error.end]
    return chunk.decode("cp1252", errors="replace"), error.end


codecs.register_error("cp1252_fallback", _cp1252_fallback)


def decode_json(response: requests.Response) -> dict:
    """Parse a JSON API response, recovering mis-encoded CP-1252 punctuation
    instead of losing it to UTF-8 decode replacement."""
    text = response.content.decode("utf-8", errors="cp1252_fallback")
    return json.loads(text)
