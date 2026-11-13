# Release notes

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
