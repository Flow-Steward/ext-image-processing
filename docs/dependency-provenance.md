# Runtime dependency provenance

Image Processing 0.2.6 bundles the extension-specific Python distribution
`onnxruntime==1.32.0+flowsteward.1`, derived from the official ONNX Runtime
1.32.0 CPU wheels in [versioned PyPI metadata](https://pypi.org/pypi/onnxruntime/1.32.0/json).
The local version distinguishes this distribution from the upstream wheel.

The upstream amd64 wheel makes the complete extension archive exceed the host's
50 MiB install limit. This distribution omits exactly one member:
`onnxruntime/capi/libonnxruntime.so.1.32.0`, the standalone C/C++ shared library.
The Python binding embeds its own inference engine and does not link that
library (verified through ELF `DT_NEEDED` on both architectures). This wheel is
for the extension's Python CPU inference; the separate C/C++ shared-library API
is unavailable. No native binary, model, operator or provider is edited.

349 upstream members per architecture remain byte-identical. The only changes
are the version assignments in `onnxruntime/__init__.py` and
`onnxruntime/capi/build_and_package_info.py`, the `METADATA` version header, and
regenerated `RECORD`. The `.dist-info` directory uses the local version.
Python bindings, inference code, optional tools, provider binaries, license and
third-party notices are retained. `onnxruntime.get_version_string()` continues
to report the unmodified native engine version, `1.32.0`.

| Target (CPython 3.12, glibc >= 2.28) | Local wheel SHA-256 | Upstream wheel SHA-256 |
| --- | --- | --- |
| Linux arm64 | `9788858f38ed253681ad8253baf900411efc3bda9235a3fa9c03039675db381f` | `e36c187006e7a7c8b8d6d57f1a209dd63f52430dca6c282b177718ad6b841054` |
| Linux amd64 | `b848bfb28f54bf19df1e7f0eea26a62c7872ef8c932828e1f413d32660fa50f8` | `99e1074c4b2197accd5073052a465361be17b89c093b8ffb6e6bd8f986c52df8` |

`extension.yaml` and `.github/requirements-test.txt` pin local versions and
SHA-256 hashes. CI force-reinstalls the complete shipped runtime offline with
hash verification. Its dependency set remains flatbuffers, NumPy >= 1.21.6,
packaging, and protobuf >= 4.25.8; symbolic and quantization extras are not enabled.

## Rebuild and audit

The shipped [recipe](../scripts/slim_onnxruntime.py) verifies the upstream input
SHA-256 before modifying anything, orders members consistently, fixes ZIP
timestamps and permissions, and regenerates every `RECORD` hash and size.
Download the two upstream wheels at the immutable URLs recorded in
[`dependency-sources.json`](../dependency-sources.json) to a separate directory,
then run this from the repository with Python 3.12:

```bash
python scripts/slim_onnxruntime.py --source-dir /tmp/onnx-upstream \
  --output-dir /tmp/onnx-rebuilt --write-provenance /tmp/onnx-provenance.json
```

The two resulting wheel hashes must match the table above.
[`onnxruntime-wheel-provenance.json`](onnxruntime-wheel-provenance.json) records
the recipe hash, original and local wheel hashes, removed-member hashes,
changed-member hashes and every byte-identical member hash. The dependency
source manifest pins that inventory's hash. Its top-level `source` and
`upstream_tag` identify the official GitHub release; exact PyPI wheel hashes
provide artifact provenance, without claiming a wheel build commit. The fixture tests reject altered
upstream input, verify the exact removal and preserved members, check every
`RECORD` entry and prove repeatable builds.

## Notices and compatibility

Both wheels retain the upstream MIT license at `onnxruntime/LICENSE`
(SHA-256 `2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c`)
and `onnxruntime/ThirdPartyNotices.txt`
(SHA-256 `d8696258afcf9df7827a5e01d6b6d55ee9b461b4e82020f5f48242deb9cc2270`).
The model and rembg adapter notices remain in `models/README.md` and `licenses/`.

The [1.32.0 release notes](https://github.com/microsoft/onnxruntime/releases/tag/v1.32.0)
remove `ACLExecutionProvider`; this extension explicitly requests only
`CPUExecutionProvider`. The bundled U2-NetP checksum, CPU thread limits, input
security limits and public image-operation contracts remain unchanged.
