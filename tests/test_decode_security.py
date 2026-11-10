"""Safe regressions for the PNG parser boundaries used by this extension."""

from __future__ import annotations

import io

import pytest
from PIL import Image

import images
from errors import ImageProcessingError


@pytest.mark.parametrize("disposal", [1, 2])
@pytest.mark.parametrize(
    "pixel_limit, error_code", [(32, "image_too_large"), (64, "unsupported_image")]
)
def test_apng_rejection_does_not_allocate_disposal_pixels(
    monkeypatch, disposal, pixel_limit, error_code
):
    # An 8x8 fixture exercises the pre-validation allocation without a large input.
    encoded = io.BytesIO()
    Image.new("RGBA", (8, 8), "red").save(
        encoded,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGBA", (8, 8), "blue")],
        disposal=disposal,
    )

    # Initialize plugin registration before watching only decoding allocations.
    Image.init()

    def no_disposal_allocation(*_args, **_kwargs):
        pytest.fail("rejected APNG allocated a disposal frame before validation")

    monkeypatch.setattr(images, "MAX_PIXELS", pixel_limit)
    monkeypatch.setattr(Image.core, "fill", no_disposal_allocation)
    with pytest.raises(ImageProcessingError) as caught:
        images.decode_image(encoded.getvalue())
    assert caught.value.code == error_code


@pytest.mark.parametrize("headers", [1, 2])
def test_png_exif_orientation_preserves_supported_headers(headers):
    exif = Image.Exif()
    exif[274] = 6
    encoded = io.BytesIO()
    Image.new("RGB", (8, 4), "red").save(
        encoded, format="PNG", exif=b"Exif\x00\x00" * (headers - 1) + exif.tobytes()
    )
    result = images.decode_image(encoded.getvalue())
    assert result.size == (4, 8)
    assert result.getpixel((0, 0)) == (255, 0, 0, 255)
    assert "exif" not in result.info


def test_png_exif_repeated_headers_are_rejected():
    # Three headers are sufficient to catch unbounded header stripping. No large
    # or deliberately expensive payload is necessary to exercise this boundary.
    exif = Image.Exif()
    exif[274] = 6
    encoded = io.BytesIO()
    Image.new("RGB", (8, 4), "red").save(
        encoded, format="PNG", exif=b"Exif\x00\x00" * 2 + exif.tobytes()
    )
    with pytest.raises(ImageProcessingError) as caught:
        images.decode_image(encoded.getvalue())
    assert caught.value.code == "invalid_image"
