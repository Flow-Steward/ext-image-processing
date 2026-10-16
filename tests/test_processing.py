from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import background
import image_processing
from errors import ImageProcessingError
from images import decode_image, dimensions, resize_image

BUNDLE = Path(__file__).resolve().parents[1]
# The final extension_host_v2 execution scope: all four keys, at most one owner.
ROOT_STEP_SCOPE = {
    "group_id": None,
    "for_each_id": None,
    "step_id": "resize_photo",
    "step_execution_id": "3f6a1c2d-9b8e-4d7c-a6f5-1e2d3c4b0001",
}
GROUP_STEP_SCOPE = {**ROOT_STEP_SCOPE, "group_id": "prepare_images"}
FOR_EACH_STEP_SCOPE = {
    **ROOT_STEP_SCOPE,
    "for_each_id": "each_photo",
    "step_execution_id": "3f6a1c2d-9b8e-4d7c-a6f5-1e2d3c4b0002",
}


def payload(
    tmp_path: Path,
    image: Image.Image,
    action: str = "upscale",
    scope: dict | None = None,
    **options,
) -> dict:
    source = tmp_path / "source.png"
    image.save(source)
    return {
        "contract_version": "extension_host_v2",
        "runtime_context": dict(FOR_EACH_STEP_SCOPE if scope is None else scope),
        "action": {
            "action_id": action,
            "input": {"artifact_handle": "artifact:input", **options},
        },
        "artifacts": {
            "inputs": [
                {
                    "kind": "artifact",
                    "artifact_id": "input",
                    "artifact_handle": "artifact:input",
                    "binding_key": "source_image",
                    "content_type": "image/png",
                    "access": {
                        "transport": "presigned_url",
                        "mode": "read",
                        "download_url": source.as_uri(),
                        "max_size_bytes": 20 * 1024 * 1024,
                    },
                }
            ],
            "outputs": [
                {
                    "kind": "artifact",
                    "artifact_id": "output",
                    "artifact_handle": "artifact:output",
                    "binding_key": "image_artifact_handle",
                    "content_type": "image/png",
                    "access": {
                        "transport": "presigned_url",
                        "mode": "write",
                        "upload_url": (tmp_path / "output.png").as_uri(),
                        "max_size_bytes": 70 * 1024 * 1024,
                    },
                }
            ],
        },
    }


def test_square_upscale_1024_to_1480_without_model(tmp_path, monkeypatch):
    def no_model():
        pytest.fail("upscale must not initialize an inference session")

    monkeypatch.setattr(background, "model_session", no_model)
    request = payload(
        tmp_path,
        Image.new("RGB", (1024, 1024), (60, 120, 180)),
        target_width=1480,
        target_height=1480,
    )
    response = image_processing.handle_payload(request)
    assert response["ok"], response
    assert response["result"]["image_artifact_handle"] == "artifact:output"
    assert response["result"]["processing_method"] == "lanczos"
    with Image.open(tmp_path / "output.png") as output:
        assert output.size == (1480, 1480)
        assert output.format == "PNG"
        assert output.getpixel((740, 740)) == (60, 120, 180, 255)


@pytest.mark.parametrize(
    ("size", "bounds", "expected"),
    [
        ((1024, 768), (1920, 1080), (1440, 1080)),
        ((768, 1024), (1920, 1080), (810, 1080)),
        ((2048, 2048), (1480, 1480), (1480, 1480)),
        ((8192, 1), (1, 1), (1, 1)),
    ],
)
def test_proportional_bounds(size, bounds, expected):
    assert resize_image(Image.new("RGBA", size), bounds).size == expected


@pytest.mark.parametrize("first_action", ["upscale", "remove_background"])
def test_independent_actions_compose_in_either_order(tmp_path, first_action):
    source = Image.new("RGBA", (128, 128), "white")
    ImageDraw.Draw(source).rounded_rectangle((30, 24, 98, 104), 10, fill=(40, 80, 160))
    request = payload(tmp_path, source, first_action, target_width=148, target_height=148)
    first = image_processing.handle_payload(request)
    assert first["ok"], first
    request["action"]["action_id"] = "remove_background" if first_action == "upscale" else "upscale"
    request["action"]["input"]["artifact_handle"] = first["result"]["image_artifact_handle"]
    request["artifacts"]["inputs"][0].update(
        {
            "artifact_id": "output",
            "artifact_handle": first["result"]["image_artifact_handle"],
            "access": {
                "transport": "presigned_url",
                "mode": "read",
                "download_url": (tmp_path / "output.png").as_uri(),
                "max_size_bytes": 20 * 1024 * 1024,
            },
        }
    )
    request["artifacts"]["outputs"][0].update(
        {
            "artifact_id": "final",
            "artifact_handle": "artifact:final",
            "access": {
                "transport": "presigned_url",
                "mode": "write",
                "upload_url": (tmp_path / "final.png").as_uri(),
                "max_size_bytes": 70 * 1024 * 1024,
            },
        }
    )
    final = image_processing.handle_payload(request)
    assert final["ok"], final
    assert final["result"]["image_artifact_handle"] == "artifact:final"
    with Image.open(tmp_path / "final.png") as output:
        assert output.size == (148, 148)
        low, high = output.getchannel("A").getextrema()
        assert low < 20
        assert high > 230


@pytest.mark.parametrize(
    "value", [0, -1, True, "1480", 3.5, None, float("inf"), float("nan"), 8193]
)
def test_invalid_dimensions(value):
    with pytest.raises(ImageProcessingError, match="integers"):
        dimensions({"target_width": value, "target_height": 1480})


def test_large_bounds_rejected_before_artifact_io(monkeypatch):
    monkeypatch.setattr(image_processing, "_read_image", lambda *_: pytest.fail("no artifact read"))
    response = image_processing.handle_payload(
        {
            "contract_version": "extension_host_v2",
            "runtime_context": dict(ROOT_STEP_SCOPE),
            "action": {
                "action_id": "upscale",
                "input": {
                    "artifact_handle": "artifact:input",
                    "target_width": 8192,
                    "target_height": 8192,
                },
            },
        }
    )
    assert response["error_code"] == "invalid_dimensions"


def test_existing_transparency_bypasses_model(tmp_path, monkeypatch):
    monkeypatch.setattr(background, "model_session", lambda: pytest.fail("no inference needed"))
    source = Image.new("RGBA", (16, 16), (120, 40, 80, 90))
    response = image_processing.handle_payload(payload(tmp_path, source, "remove_background"))
    assert response["ok"], response
    assert response["result"]["processing_method"] == "existing_transparency"
    with Image.open(tmp_path / "output.png") as output:
        assert output.tobytes() == source.tobytes()


def test_upscale_keeps_transparency(tmp_path):
    image = Image.new("RGBA", (16, 16), (30, 60, 90, 128))
    response = image_processing.handle_payload(
        payload(tmp_path, image, target_width=32, target_height=32)
    )
    assert response["ok"]
    with Image.open(tmp_path / "output.png") as output:
        assert output.getchannel("A").getextrema() == (128, 128)


@pytest.mark.parametrize("constant", [0.0, 1.0, float("nan")])
def test_model_constant_and_invalid_predictions(monkeypatch, constant):
    class Session:
        def get_inputs(self):
            return [type("Input", (), {"name": "input"})()]

        def run(self, _, inputs):
            assert inputs["input"].shape == (1, 3, 320, 320)
            assert np.isfinite(inputs["input"]).all()
            return [np.full((1, 1, 320, 320), constant, dtype=np.float32)]

    monkeypatch.setattr(background, "model_session", lambda: Session())
    source = Image.new("RGBA", (32, 24), (0, 0, 0, 128))
    if np.isnan(constant):
        with pytest.raises(ImageProcessingError, match="invalid mask"):
            background.remove_background(source)
    else:
        output = background.remove_background(source)
        expected = 128 if constant else 0
        assert output.getchannel("A").getextrema() == (expected, expected)
        assert output.size == source.size


def test_missing_model_is_a_structured_error(tmp_path, monkeypatch):
    monkeypatch.setattr(background, "MODEL_PATH", tmp_path / "missing.onnx")
    background.model_session.cache_clear()
    response = image_processing.handle_payload(
        payload(tmp_path, Image.new("RGB", (16, 16)), "remove_background")
    )
    assert response["error_code"] == "model_unavailable"
    assert not (tmp_path / "output.png").exists()


def test_corrupt_model_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "corrupt.onnx"
    path.write_bytes(b"invalid")
    monkeypatch.setattr(background, "MODEL_PATH", path)
    with pytest.raises(ImageProcessingError, match="checksum"):
        background.verify_model()


def test_real_cpu_model_produces_finite_alpha():
    background.model_session.cache_clear()
    image = Image.new("RGBA", (64, 48), "white")
    output = background.remove_background(image)
    assert output.size == image.size
    assert output.mode == "RGBA"
    assert background.model_session().get_providers() == ["CPUExecutionProvider"]
    assert np.isfinite(np.asarray(output)).all()


def test_invalid_and_animated_images():
    with pytest.raises(ImageProcessingError, match="Cannot decode"):
        decode_image(b"not an image")
    encoded = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(
        encoded, format="PNG", save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")]
    )
    with pytest.raises(ImageProcessingError, match="Animated"):
        decode_image(encoded.getvalue())


def test_exif_orientation_applied_before_resize():
    image = Image.new("RGB", (40, 20))
    exif = Image.Exif()
    exif[274] = 6
    encoded = io.BytesIO()
    image.save(encoded, format="JPEG", exif=exif)
    decoded = decode_image(encoded.getvalue())
    assert decoded.size == (20, 40)
    assert resize_image(decoded, (100, 100)).size == (50, 100)


def test_byte_limit_enforced_while_streaming(monkeypatch):
    monkeypatch.setattr(image_processing, "INPUT_MAX_BYTES", 3)
    monkeypatch.setattr(
        image_processing, "stream_artifact_bytes", lambda *a, **k: iter([b"ab", b"cd"])
    )
    with pytest.raises(ImageProcessingError, match="20 MiB"):
        image_processing._read_image({}, "artifact:input")


@pytest.mark.parametrize(
    "raw",
    [
        "{invalid",
        "[]",
        "null",
        '{"action": {"action_id": "unknown"}}',
        json.dumps(
            {
                "contract_version": "extension_host_v2",
                "runtime_context": ROOT_STEP_SCOPE,
                "action": {"action_id": "unknown"},
            }
        ),
    ],
)
def test_entrypoint_returns_structured_errors(raw):
    proc = subprocess.run(
        [sys.executable, str(BUNDLE / "main.py")],
        input=raw,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    response = json.loads(proc.stdout)
    assert response["ok"] is False
    assert "Traceback" not in proc.stderr


@pytest.mark.parametrize("scope", [ROOT_STEP_SCOPE, GROUP_STEP_SCOPE, FOR_EACH_STEP_SCOPE])
@pytest.mark.parametrize("action", ["upscale", "check_size"])
def test_every_final_scope_owner_reads_and_writes_artifacts(tmp_path, scope, action):
    request = payload(
        tmp_path,
        Image.new("RGB", (64, 32), (10, 20, 30)),
        action,
        scope=scope,
        target_width=128,
        target_height=128,
    )

    response = image_processing.handle_payload(request)

    assert response["ok"], response
    if action == "check_size":
        assert response["result"]["width"] == 64
        assert response["result"]["needs_resize"] is True
        assert not (tmp_path / "output.png").exists()
    else:
        assert response["result"]["image_artifact_handle"] == "artifact:output"
        with Image.open(tmp_path / "output.png") as output:
            assert output.size == (128, 64)


@pytest.mark.parametrize(
    ("contract_version", "scope", "reason"),
    [
        ("extension_host_v1", FOR_EACH_STEP_SCOPE, "Unsupported host contract"),
        ("", FOR_EACH_STEP_SCOPE, "Unsupported host contract"),
        (
            "extension_host_v2",
            {k: v for k, v in FOR_EACH_STEP_SCOPE.items() if k != "for_each_id"},
            "misses execution scope",
        ),
        (
            "extension_host_v2",
            {**FOR_EACH_STEP_SCOPE, "group_id": "prepare_images"},
            "both a Group and a For each",
        ),
        (
            "extension_host_v2",
            {**ROOT_STEP_SCOPE, "step_execution_id": None},
            "without its logical execution",
        ),
    ],
)
def test_foreign_or_incomplete_envelope_is_refused_before_any_artifact_io(
    tmp_path, monkeypatch, contract_version, scope, reason
):
    def no_artifact_io(*_args, **_kwargs):
        pytest.fail("a refused envelope must not read or write an artifact")

    monkeypatch.setattr(image_processing, "stream_artifact_bytes", no_artifact_io)
    monkeypatch.setattr(image_processing, "write_artifact_bytes", no_artifact_io)
    request = payload(tmp_path, Image.new("RGB", (16, 16)), "upscale", scope=scope)
    request["action"]["input"].update(target_width=32, target_height=32)
    request["contract_version"] = contract_version

    response = image_processing.handle_payload(request)

    assert response["ok"] is False
    assert response["error_code"] == "invalid_host_envelope"
    assert reason in response["error"]
    assert response["definitely_no_external_effect"] is True
    assert not (tmp_path / "output.png").exists()
