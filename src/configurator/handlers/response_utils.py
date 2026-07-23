#!/usr/bin/env python3
"""Shared response helpers for handler payload consistency."""

from typing import Any, Callable, Dict, Optional, Tuple


def build_error_payload(
    message: str,
    error: str,
    data: Optional[Dict[str, Any]] = None,
    system_error: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a normalized API error payload."""
    payload: Dict[str, Any] = {
        "status": "error",
        "message": message,
        "error": error,
        "data": data.copy() if data else {},
    }
    if system_error:
        payload["data"]["system_error"] = system_error
    return payload


def error_response(
    jsonify_fn: Callable[[Dict[str, Any]], Any],
    message: str,
    error: str,
    http_status: int,
    data: Optional[Dict[str, Any]] = None,
    system_error: Optional[str] = None,
) -> Tuple[Any, int]:
    """Create a normalized Flask-style error response tuple."""
    payload = build_error_payload(message, error, data=data, system_error=system_error)
    return jsonify_fn(payload), http_status
