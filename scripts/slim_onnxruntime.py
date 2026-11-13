#!/usr/bin/env python3
"""Rebuild pinned ORT wheels for the extension's Python-only CPU inference.

Only the separate C/C++ shared library is omitted. Python bindings, operators,
providers and upstream notices are preserved; local version metadata and RECORD
are regenerated. No native binary is edited.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

UPSTREAM_VERSION = "1.32.0"
LOCAL_VERSION = "1.32.0+flowsteward.1"
REMOVED = "onnxruntime/capi/libonnxruntime.so.1.32.0"
SOURCES = {
    "onnxruntime-1.32.0-cp312-cp312-manylinux_2_28_aarch64.whl": {
        "sha256": "e36c187006e7a7c8b8d6d57f1a209dd63f52430dca6c282b177718ad6b841054",
        "url": "https://files.pythonhosted.org/packages/4a/8f/1e43fb994513c7c7a9c6965272ef89d963c1bd4080993a6267bf913701d1/onnxruntime-1.32.0-cp312-cp312-manylinux_2_28_aarch64.whl",
    },
    "onnxruntime-1.32.0-cp312-cp312-manylinux_2_28_x86_64.whl": {
        "sha256": "99e1074c4b2197accd5073052a465361be17b89c093b8ffb6e6bd8f986c52df8",
        "url": "https://files.pythonhosted.org/packages/a3/81/55845186c20cba59f614991f4065dea148e48eeb9749893768c85ce64327/onnxruntime-1.32.0-cp312-cp312-manylinux_2_28_x86_64.whl",
    },
}
OLD_INFO = f"onnxruntime-{UPSTREAM_VERSION}.dist-info/"
NEW_INFO = f"onnxruntime-{LOCAL_VERSION}.dist-info/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rebuild_wheel(source: Path, output_dir: Path, expected_sha256: str) -> Path:
    original = source.read_bytes()
    if sha256(original) != expected_sha256:
        raise ValueError(f"{source.name}: upstream SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate upstream wheel member")
        files = {name: archive.read(name) for name in names}
    # A missing expected member indicates a different upstream packaging layout.
    del files[REMOVED]
    del files[OLD_INFO + "RECORD"]
    for name in ("onnxruntime/__init__.py", "onnxruntime/capi/build_and_package_info.py"):
        data, count = re.subn(
            rb"(?m)^(__version__\s*=\s*['\"])1\.32\.0(['\"])",
            lambda match: match[1] + LOCAL_VERSION.encode() + match[2],
            files[name],
        )
        if count != 1:
            raise ValueError(f"{name}: expected exactly one upstream version assignment")
        files[name] = data
    name = OLD_INFO + "METADATA"
    data, count = re.subn(rb"(?m)^Version: 1\.32\.0$", b"Version: " + LOCAL_VERSION.encode(), files[name])
    if count != 1:
        raise ValueError("Expected exactly one upstream METADATA Version header")
    files[name] = data
    files = {name.replace(OLD_INFO, NEW_INFO, 1): data for name, data in files.items()}
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, len(data)))
    writer.writerow((NEW_INFO + "RECORD", "", ""))
    files[NEW_INFO + "RECORD"] = record.getvalue().encode()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / source.name.replace(f"-{UPSTREAM_VERSION}-", f"-{LOCAL_VERSION}-", 1)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return output


def provenance(source: Path, output: Path) -> dict:
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        original = {name: before.read(name) for name in before.namelist()}
        result = {name: after.read(name) for name in after.namelist()}
    unchanged, changed = {}, []
    for name, data in sorted(original.items()):
        target = name.replace(OLD_INFO, NEW_INFO, 1)
        if name == REMOVED:
            continue
        if result[target] == data:
            unchanged[target] = sha256(data)
        else:
            changed.append({"source": name, "target": target, "upstream_sha256": sha256(data), "local_sha256": sha256(result[target])})
    return {
        "upstream": {"filename": source.name, **SOURCES[source.name]},
        "local": {"filename": output.name, "version": LOCAL_VERSION, "sha256": sha256(output.read_bytes())},
        "removed": [{"path": REMOVED, "sha256": sha256(original[REMOVED]), "bytes": len(original[REMOVED])}],
        "changed": changed,
        "unchanged_members_sha256": unchanged,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path, help="Directory containing the two original pinned PyPI wheels")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--write-provenance", type=Path)
    args = parser.parse_args()
    records = []
    for name, metadata in SOURCES.items():
        source = args.source_dir / name
        output = rebuild_wheel(source, args.output_dir, metadata["sha256"])
        records.append(provenance(source, output))
        print(f"{output.name}: sha256:{sha256(output.read_bytes())}")
    if args.write_provenance:
        args.write_provenance.write_text(json.dumps({"source": "https://github.com/microsoft/onnxruntime", "upstream_tag": "v" + UPSTREAM_VERSION, "recipe": "scripts/slim_onnxruntime.py", "recipe_sha256": sha256(Path(__file__).read_bytes()), "upstream_version": UPSTREAM_VERSION, "local_version": LOCAL_VERSION, "wheels": records}, indent=2) + "\n")


if __name__ == "__main__":
    main()
