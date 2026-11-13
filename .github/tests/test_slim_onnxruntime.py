"""The wheel recipe must preserve the Python runtime and produce honest wheel metadata."""
from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("slim_onnxruntime", ROOT / "scripts/slim_onnxruntime.py")
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


@pytest.fixture
def upstream(tmp_path):
    # A pybind binary, provider binary, model/operator-related Python tools and
    # both notices catch any recipe that prunes more than the unused C API.
    files = {
        "onnxruntime/__init__.py": b'__version__ = "1.32.0"\n',
        "onnxruntime/capi/build_and_package_info.py": b"package_name = 'onnxruntime'\n__version__ = '1.32.0'\n",
        "onnxruntime/capi/libonnxruntime.so.1.32.0": b"standalone C API",
        "onnxruntime/capi/onnxruntime_pybind11_state.cpython-312-x86_64-linux-gnu.so": b"all Python operators",
        "onnxruntime/capi/libonnxruntime_providers_shared.so": b"shared providers",
        "onnxruntime/quantization/quantize.py": b"keep optional tools too\n",
        "onnxruntime/LICENSE": b"MIT license\n",
        "onnxruntime/ThirdPartyNotices.txt": b"all upstream notices\n",
        "onnxruntime-1.32.0.dist-info/METADATA": b"Metadata-Version: 2.4\nName: onnxruntime\nVersion: 1.32.0\nRequires-Dist: numpy>=1.21.6\n\nUpstream description\n",
        "onnxruntime-1.32.0.dist-info/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp312-cp312-manylinux_2_28_x86_64\n",
        "onnxruntime-1.32.0.dist-info/RECORD": b"old record\n",
    }
    source = tmp_path / "onnxruntime-1.32.0-cp312-cp312-manylinux_2_28_x86_64.whl"
    with zipfile.ZipFile(source, "w") as wheel:
        for name, data in files.items():
            wheel.writestr(name, data)
    return source, files, hashlib.sha256(source.read_bytes()).hexdigest()


def test_rebuild_preserves_runtime_and_notices_and_records_every_member(upstream, tmp_path):
    source, originals, digest = upstream
    result = recipe.rebuild_wheel(source, tmp_path / "built", digest)
    assert result is not None, "the wheel recipe must produce the installable local distribution"
    assert result.name == "onnxruntime-1.32.0+flowsteward.1-cp312-cp312-manylinux_2_28_x86_64.whl"
    with zipfile.ZipFile(result) as wheel:
        files = {name: wheel.read(name) for name in wheel.namelist()}
    old_info = "onnxruntime-1.32.0.dist-info/"
    new_info = "onnxruntime-1.32.0+flowsteward.1.dist-info/"
    expected_names = {
        name.replace(old_info, new_info)
        for name in originals
        if name != "onnxruntime/capi/libonnxruntime.so.1.32.0"
    }
    assert set(files) == expected_names
    version_files = {"onnxruntime/__init__.py", "onnxruntime/capi/build_and_package_info.py", old_info + "METADATA"}
    for name, data in originals.items():
        if name == "onnxruntime/capi/libonnxruntime.so.1.32.0" or name == old_info + "RECORD":
            continue
        expected = data.replace(b"1.32.0", b"1.32.0+flowsteward.1") if name in version_files else data
        assert files[name.replace(old_info, new_info)] == expected, name
    rows = list(csv.reader(io.StringIO(files[new_info + "RECORD"].decode())))
    assert len(rows) == len(files)
    assert {row[0] for row in rows} == set(files)
    for name, digest, size in rows:
        if name == new_info + "RECORD":
            assert digest == size == ""
        else:
            expected = base64.urlsafe_b64encode(hashlib.sha256(files[name]).digest()).rstrip(b"=").decode()
            assert digest == "sha256=" + expected
            assert int(size) == len(files[name])
    assert source.read_bytes(), "the upstream input stays available for audit"


def test_rebuild_is_byte_reproducible(upstream, tmp_path):
    source, _, digest = upstream
    first = recipe.rebuild_wheel(source, tmp_path / "first", digest)
    second = recipe.rebuild_wheel(source, tmp_path / "second", digest)
    assert first is not None and second is not None
    assert first.read_bytes() == second.read_bytes()


def test_rebuild_rejects_unverified_input_before_writing_any_output(upstream, tmp_path):
    source, _, _ = upstream
    out = tmp_path / "refused"
    with pytest.raises(ValueError, match="SHA-256"):
        recipe.rebuild_wheel(source, out, "0" * 64)
    assert not out.exists()


def test_shipped_wheels_match_audited_member_inventory_and_recipe():
    import json

    inventory_path = ROOT / "docs/onnxruntime-wheel-provenance.json"
    inventory = json.loads(inventory_path.read_text())
    # The dependency monitor consumes these as upstream release identity,
    # separate from the immutable PyPI wheel artifact hashes below.
    assert inventory.get("source") == "https://github.com/microsoft/onnxruntime"
    assert inventory.get("upstream_tag") == "v" + inventory["upstream_version"]
    assert hashlib.sha256((ROOT / inventory["recipe"]).read_bytes()).hexdigest() == inventory["recipe_sha256"]
    sources = json.loads((ROOT / "dependency-sources.json").read_text())["dependencies"]
    assert len(sources) == len(inventory["wheels"]) == 2
    assert {row["wheel_filename"] for row in sources} == {row["local"]["filename"] for row in inventory["wheels"]}
    for row in sources:
        assert row["patch_sha256"] == hashlib.sha256((ROOT / row["patches"]).read_bytes()).hexdigest()
    for row in inventory["wheels"]:
        wheel_path = ROOT / "wheels" / row["local"]["filename"]
        assert hashlib.sha256(wheel_path.read_bytes()).hexdigest() == row["local"]["sha256"]
        with zipfile.ZipFile(wheel_path) as wheel:
            expected_members = set(row["unchanged_members_sha256"]) | {change["target"] for change in row["changed"]}
            assert set(wheel.namelist()) == expected_members
            assert len(row["removed"]) == 1
            assert row["removed"][0]["path"] == "onnxruntime/capi/libonnxruntime.so.1.32.0"
            for name, digest in row["unchanged_members_sha256"].items():
                assert hashlib.sha256(wheel.read(name)).hexdigest() == digest, name
            for change in row["changed"]:
                assert hashlib.sha256(wheel.read(change["target"])).hexdigest() == change["local_sha256"]
