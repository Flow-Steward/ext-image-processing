"""Bounded image decoding and proportional, non-generative resizing."""

from __future__ import annotations

import io
import warnings
from typing import cast

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from errors import ImageProcessingError

MAX_PIXELS = 16_777_216
MAX_DIMENSION = 8192
OUTPUT_MAX_BYTES = 70 * 1024 * 1024
SUPPORTED_FORMATS = {"PNG", "JPEG", "WEBP"}
RESIZE_MODES = {"resize", "fit_canvas"}


def dimensions(options: dict, default: tuple[int, int] = (1920, 1080)) -> tuple[int, int]:
    values = (options.get("target_width", default[0]), options.get("target_height", default[1]))
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 1 <= value <= MAX_DIMENSION
            or value != int(value)
        ):
            raise ImageProcessingError(
                "invalid_dimensions",
                f"Width and height must be integers from 1 to {MAX_DIMENSION}.",
            )
    width, height = (int(value) for value in values)
    if width * height > MAX_PIXELS:
        raise ImageProcessingError("invalid_dimensions", "Requested bounds exceed 16 megapixels.")
    return width, height


def resize_mode(options: dict) -> str:
    value = options.get("resize_mode", "resize")
    if value not in RESIZE_MODES:
        raise ImageProcessingError(
            "invalid_resize_mode", "resize_mode must be resize or fit_canvas."
        )
    return value


def canvas_fill(options: dict) -> tuple[int, int, int, int]:
    value = options.get("canvas_color", "white")
    if value == "white":
        return (255, 255, 255, 255)
    if value == "transparent":
        return (255, 255, 255, 0)
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            return (
                int(value[1:3], 16),
                int(value[3:5], 16),
                int(value[5:7], 16),
                255,
            )
        except ValueError as exc:
            raise ImageProcessingError(
                "invalid_canvas_color",
                "canvas_color must be white, transparent, or #RRGGBB.",
            ) from exc
    raise ImageProcessingError(
        "invalid_canvas_color", "canvas_color must be white, transparent, or #RRGGBB."
    )


def decode_image(body: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(body), formats=list(SUPPORTED_FORMATS)) as source:
                if source.width * source.height > MAX_PIXELS:
                    raise ImageProcessingError("image_too_large", "Input exceeds 16 megapixels.")
                if getattr(source, "is_animated", False):
                    raise ImageProcessingError(
                        "unsupported_image", "Animated images are not supported."
                    )
                if source.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "CMYK"}:
                    raise ImageProcessingError(
                        "unsupported_image", "Only 8-bit images are supported."
                    )
                source.load()
                oriented = ImageOps.exif_transpose(source)
                if oriented.mode == "CMYK" and oriented.info.get("icc_profile"):
                    converted = ImageCms.profileToProfile(
                        oriented,
                        ImageCms.ImageCmsProfile(io.BytesIO(oriented.info["icc_profile"])),
                        ImageCms.createProfile("sRGB"),
                        outputMode="RGB",
                    )
                    if converted is not None:  # None only for an in-place conversion
                        oriented = converted
                result = oriented.convert("RGBA")
                profile = (
                    oriented.info.get("icc_profile") if oriented.mode in {"RGB", "RGBA"} else None
                )
                result.info.clear()
                if profile:
                    result.info["icc_profile"] = profile
                return result
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ImageProcessingError(
            "image_too_large", "Image exceeds the decoded pixel limit."
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ImageCms.PyCMSError) as exc:
        raise ImageProcessingError(
            "invalid_image", "Cannot decode a valid PNG, JPEG or WebP image."
        ) from exc


def resize_image(image: Image.Image, bounds: tuple[int, int]) -> Image.Image:
    scale = min(bounds[0] / image.width, bounds[1] / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, resample=Image.Resampling.LANCZOS)


def fit_canvas(
    image: Image.Image, bounds: tuple[int, int], fill: tuple[int, int, int, int]
) -> Image.Image:
    resized = resize_image(image, bounds)
    canvas = Image.new("RGBA", bounds, fill)
    offset = ((bounds[0] - resized.width) // 2, (bounds[1] - resized.height) // 2)
    canvas.alpha_composite(resized, dest=offset)
    return canvas


def has_transparency(image: Image.Image) -> bool:
    # A single band's extrema is one (min, max) pair.
    low, _high = cast("tuple[int, int]", image.getchannel("A").getextrema())
    return low < 255


def encode_png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=6, icc_profile=image.info.get("icc_profile"))
    if output.tell() > OUTPUT_MAX_BYTES:
        raise ImageProcessingError("output_too_large", "PNG output exceeds 70 MiB.")
    return output.getvalue()
