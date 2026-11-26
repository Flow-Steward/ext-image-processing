# Release notes

## 0.2.10

- Update the bundled and CI-tested `packaging` wheel to 26.4 on Linux amd64 and arm64. Both targets use the official [PyPI wheel](https://pypi.org/project/packaging/26.4/) with its SHA-256 pin.

[Changes from 0.2.9](https://github.com/Flow-Steward/ext-image-processing/compare/v0.2.9...v0.2.10)

## 0.2.9

- Identify Flow Steward as the extension publisher and provide the extension repository's issue tracker in both manifest and descriptor support metadata.

[Changes from 0.2.8](https://github.com/Flow-Steward/ext-image-processing/compare/v0.2.8...v0.2.9)

## 0.2.8

- Update bundled NumPy from 2.5.4 to 2.5.5 using the official CPython 3.12 Linux amd64 and arm64 wheels with exact SHA-256 pins.
- Verify the existing image operations and CPU model through offline runtime installs on native Linux amd64 and arm64 CI runners.
- Record provenance for the unchanged Flow Steward icon.

## 0.2.7

- Added a Support tab with links for reporting a problem, asking a question or requesting a feature in this extension's GitHub repository, and what to include in a report.
- Added the issue tracker as the extension's support link.

## 0.2.6

- Upgrade the bundled ONNX Runtime CPU dependency from 1.31.1 to 1.32.0 for
  Linux amd64 and arm64, using `1.32.0+flowsteward.1` wheels with exact SHA-256 pins.
- Omit only the unused standalone C/C++ library to fit the existing archive
  limit. Preserve the complete Python inference binding, operators and providers;
  include the reproducible recipe and upstream-to-local member provenance.
- Hash-verify the complete offline runtime dependency set during CI testing.
- Document wheel provenance and the upstream license and third-party notices
  retained inside both wheels.
- Preserve the bundled U2-NetP model checksum, CPU-only inference settings,
  image security limits, and all image-operation inputs and outputs.
