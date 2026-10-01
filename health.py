"""Check installed CPU dependencies and bundled model without network access."""

from __future__ import annotations

import json
import sys


def check_health() -> dict:
    try:
        import numpy
        import onnxruntime
        import PIL

        from background import model_session

        model_session()
    except (ImportError, ValueError, RuntimeError, OSError) as exc:
        return {
            "ok": False,
            "status": "unhealthy",
            "detail": (
                f"CPU dependencies or model unavailable: {type(exc).__name__}: {exc}; "
                f"path={sys.path[:5]}"
            ),
        }
    return {
        "ok": True,
        "status": "healthy",
        "pillow": PIL.__version__,
        "numpy": numpy.__version__,
        "onnxruntime": onnxruntime.__version__,
        "provider": "CPUExecutionProvider",
    }


if __name__ == "__main__":
    result = check_health()
    print(json.dumps(result, separators=(",", ":")))
    raise SystemExit(0 if result["ok"] else 2)
