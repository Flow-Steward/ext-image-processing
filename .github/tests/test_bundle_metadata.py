"""Published bundle metadata identifies the extension maintainer and support channel."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SUPPORT_URL = "https://github.com/Flow-Steward/ext-image-processing/issues"


@pytest.mark.parametrize("path", ["extension.yaml", "extension-descriptor.yaml"])
def test_bundle_publisher_and_support_identify_the_maintainer(path):
    metadata = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    vendor = metadata.get("vendor", {})
    publisher = vendor.get("vendor_name") or vendor.get("name") or metadata.get("vendor_name")
    support_url = vendor.get("support_url") or metadata.get("support_url")

    assert publisher == "Flow Steward"
    assert support_url == SUPPORT_URL


def test_bundle_manifest_and_descriptor_versions_match():
    manifest = yaml.safe_load((ROOT / "extension.yaml").read_text(encoding="utf-8"))
    descriptor = yaml.safe_load((ROOT / "extension-descriptor.yaml").read_text(encoding="utf-8"))

    assert manifest["version"] == descriptor["release_version"]
