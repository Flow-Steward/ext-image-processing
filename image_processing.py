"""Workflow actions using host-issued artifact grants only."""

from __future__ import annotations

import logging
from typing import Any

from flowsteward_extension_sdk.artifacts import (
    ArtifactAccessError,
    stream_artifact_bytes,
    write_artifact_bytes,
)

from errors import ImageProcessingError, error_response
from images import (
    canvas_fill,
    decode_image,
    dimensions,
    encode_png,
    fit_canvas,
    has_transparency,
    resize_image,
    resize_mode,
)

INPUT_MAX_BYTES = 20 * 1024 * 1024
ARTIFACT_TIMEOUT_SECONDS = 10
LOGGER = logging.getLogger(__name__)


def handle_payload(payload: Any) -> dict:
    try:
        return {"ok": True, "result": process_image(payload)}
    except ImageProcessingError as exc:
        LOGGER.warning("image_processing_rejected code=%s", exc.code)
        return error_response(exc.code, str(exc))
    except ArtifactAccessError:
        LOGGER.warning("image_processing_artifact_access_failed")
        return error_response("artifact_access_failed", "Cannot access the granted image artifact.")
    except (OSError, RuntimeError, ValueError):
        LOGGER.warning("image_processing_failed")
        return error_response("processing_failed", "Image processing failed.")


def process_image(payload: Any) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("action"), dict):
        raise ImageProcessingError("invalid_payload", "An action object is required.")
    action = payload["action"]
    action_id = action.get("action_id")
    options = action.get("input")
    if action_id not in ("upscale", "remove_background", "check_size") or not isinstance(
        options, dict
    ):
        raise ImageProcessingError(
            "invalid_payload", "A supported action and input object are required."
        )
    handle = options.get("artifact_handle")
    if not isinstance(handle, str) or not handle.strip():
        raise ImageProcessingError("invalid_payload", "An image artifact_handle is required.")
    bounds = dimensions(options, default=(2048, 2048)) if action_id == "check_size" else None
    bounds = dimensions(options) if action_id == "upscale" else bounds
    mode = resize_mode(options) if action_id == "upscale" else "resize"
    fill = canvas_fill(options) if action_id == "upscale" and mode == "fit_canvas" else None
    keep_transparency = options.get("keep_existing_transparency", True)
    if not isinstance(keep_transparency, bool):
        raise ImageProcessingError(
            "invalid_payload", "keep_existing_transparency must be a boolean."
        )
    image = decode_image(_read_image(payload, handle))
    original_width, original_height = image.size
    if action_id == "check_size":
        return _size_response(image, bounds)
    if bounds is not None and mode == "fit_canvas":
        image = fit_canvas(image, bounds, fill)
        method = "lanczos_fit_canvas"
    elif bounds is not None:
        image = resize_image(image, bounds)
        method = "lanczos"
    elif keep_transparency and has_transparency(image):
        method = "existing_transparency"
    else:
        from background import remove_background

        image = remove_background(image)
        method = "u2netp_cpu"
    body = encode_png(image)
    artifact = write_artifact_bytes(
        payload,
        body,
        binding_key="image_artifact_handle",
        content_type="image/png",
        timeout_seconds=ARTIFACT_TIMEOUT_SECONDS,
    )
    return {
        "image_artifact_handle": artifact["artifact_handle"],
        "width": image.width,
        "height": image.height,
        "original_width": original_width,
        "original_height": original_height,
        "has_transparency": has_transparency(image),
        "processing_method": method,
        "size_bytes": len(body),
    }


def _size_response(image, bounds: tuple[int, int] | None) -> dict:
    target_width, target_height = bounds or (image.width, image.height)
    resized = resize_image(image, (target_width, target_height))
    exact_match = image.width == target_width and image.height == target_height
    needs_padding = resized.size != (target_width, target_height)
    return {
        "width": image.width,
        "height": image.height,
        "target_width": target_width,
        "target_height": target_height,
        "exact_match": exact_match,
        "fits_within_target": image.width <= target_width and image.height <= target_height,
        "needs_resize": resized.size != image.size,
        "needs_padding": needs_padding,
        "recommended_resize_mode": "resize" if exact_match else "fit_canvas",
    }


def _read_image(payload: dict, handle: str) -> bytes:
    body = bytearray()
    for chunk in stream_artifact_bytes(
        payload,
        artifact_id=handle,
        binding_key="source_image",
        timeout_seconds=ARTIFACT_TIMEOUT_SECONDS,
    ):
        if len(body) + len(chunk) > INPUT_MAX_BYTES:
            raise ImageProcessingError("input_too_large", "Input image exceeds 20 MiB.")
        body.extend(chunk)
    return bytes(body)
