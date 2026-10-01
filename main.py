"""Flow Steward subprocess entrypoint."""

from __future__ import annotations

import json
import sys

from errors import error_response

MAX_ENVELOPE_BYTES = 1024 * 1024


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_ENVELOPE_BYTES + 1)
    if len(raw) > MAX_ENVELOPE_BYTES:
        response = error_response("invalid_payload", "Action envelope exceeds 1 MiB.")
    else:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            response = error_response(
                "invalid_payload", "A valid JSON action envelope is required."
            )
        else:
            try:
                from image_processing import handle_payload
            except ImportError:
                response = error_response(
                    "processing_failed", "Image processing dependencies are not installed."
                )
            else:
                response = handle_payload(payload)
    print(json.dumps(response, separators=(",", ":"), allow_nan=False))
    return 0 if response["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
