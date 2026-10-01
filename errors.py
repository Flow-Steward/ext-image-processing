"""Stable workflow-facing image processing errors."""

from __future__ import annotations


class ImageProcessingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def error_response(code: str, message: str) -> dict:
    return {
        "ok": False,
        "error_code": code,
        "error": message,
        "errors": [{"code": code, "message": message}],
    }
