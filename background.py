"""U2-NetP inference on CPU; normalization follows rembg's U2netpSession.

Model and upstream notices are distributed in models/ and licenses/.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from errors import ImageProcessingError

MODEL_PATH = Path(__file__).resolve().parent / "models" / "u2netp.onnx"
MODEL_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"
MODEL_SIZE = (320, 320)


def verify_model() -> Path:
    try:
        with MODEL_PATH.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        raise ImageProcessingError(
            "model_unavailable", "Bundled U2-NetP model is missing."
        ) from exc
    if digest != MODEL_SHA256:
        raise ImageProcessingError(
            "model_unavailable", "Bundled U2-NetP model checksum is invalid."
        )
    return MODEL_PATH


@lru_cache(maxsize=1)
def model_session() -> Any:
    model_path = verify_model()
    try:
        import onnxruntime as ort
        from onnxruntime.capi.onnxruntime_pybind11_state import Fail, InvalidGraph, RuntimeException
    except ImportError as exc:
        raise ImageProcessingError(
            "model_unavailable", "CPU inference dependencies are not installed."
        ) from exc
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 3
    try:
        return ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
    except (Fail, InvalidGraph, RuntimeException) as exc:
        raise ImageProcessingError(
            "model_unavailable", "Cannot initialize the bundled CPU model."
        ) from exc


def remove_background(image: Image.Image) -> Image.Image:
    session = model_session()
    import numpy as np
    from onnxruntime.capi.onnxruntime_pybind11_state import Fail, InvalidArgument, RuntimeException

    # Invisible source colors must not affect foreground segmentation.
    opaque = Image.alpha_composite(Image.new("RGBA", image.size, "white"), image).convert("RGB")
    sample = np.asarray(opaque.resize(MODEL_SIZE, Image.Resampling.LANCZOS), dtype=np.float32)
    sample /= max(float(sample.max()), 1e-6)
    sample -= np.array([0.485, 0.456, 0.406], dtype=np.float32)
    sample /= np.array([0.229, 0.224, 0.225], dtype=np.float32)
    tensor = np.ascontiguousarray(sample.transpose(2, 0, 1)[None])
    try:
        prediction = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    except (Fail, InvalidArgument, RuntimeException) as exc:
        raise ImageProcessingError("processing_failed", "Background segmentation failed.") from exc
    if prediction.shape != MODEL_SIZE or not np.isfinite(prediction).all():
        raise ImageProcessingError(
            "processing_failed", "Background model returned an invalid mask."
        )
    low, high = float(prediction.min()), float(prediction.max())
    if high - low > 1e-6:
        prediction = (prediction - low) / (high - low)
    mask = Image.fromarray((np.clip(prediction, 0, 1) * 255).astype(np.uint8))
    mask = mask.resize(image.size, Image.Resampling.LANCZOS)
    result = image.copy()
    result.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    return result
