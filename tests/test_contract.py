from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import yaml

BUNDLE = Path(__file__).resolve().parents[1]


# The host compiling this bundle, validating its contract and its wheel lock is Core's
# own test (tests/unit/test_discogs_and_image_processing_bundle_contracts.py): a
# bundle's tests run standalone, without the monorepo.


def test_bundled_model_matches_checksum():
    from background import MODEL_PATH, MODEL_SHA256

    assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == MODEL_SHA256


def test_actions_forms_and_artifact_policy_match():
    def load(name):
        return yaml.safe_load((BUNDLE / name).read_text())

    actions = load("ui/actions/actions.yaml")["actions"]
    operations = load("contracts/operation_manifest.yaml")["operations"]
    policies = load("contracts/artifact_policies.yaml")["policies"]
    forms = load("contracts/step_ui_manifest.yaml")["forms"]
    expected = {"upscale", "remove_background", "check_size"}
    assert {row["action_id"] for row in actions if row["workflow_visible"]} == expected
    for rows in (operations, policies, forms):
        assert {row["operation_id"] for row in rows} == expected
    for policy in policies:
        assert policy["inputs"][0]["field"] == "artifact_handle"
        if policy["operation_id"] != "check_size":
            assert policy["outputs"][0]["binding_key"] == "image_artifact_handle"
            assert policy["outputs"][0]["content_type"] == "image/png"


def test_logo_is_a_square_png_within_the_host_limits():
    # Core requires icon.png at the bundle root: PNG, square, 32-512 px, <= 100 KB.
    data = (BUNDLE / "icon.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    assert width == height
    assert 32 <= width <= 512
    assert len(data) <= 100 * 1024
