from functools import wraps
from flask import request, jsonify
from config import Config


def require_api_key(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not Config.API_KEY:
            return jsonify({
                "error": {
                    "message": "Gateway API_KEY is not configured",
                    "type": "server_error"
                }
            }), 500

        token = ""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        elif not token:
            token = request.headers.get("X-API-Key", "").strip()

        if token != Config.API_KEY:
            return jsonify({
                "error": {
                    "message": "Invalid or missing API key",
                    "type": "authentication_error"
                }
            }), 401

        return fn(*args, **kwargs)

    return decorated
