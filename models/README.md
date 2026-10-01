# U2-NetP

Bundled ONNX model: `u2netp.onnx` (4,574,861 bytes).

Source: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx

SHA-256: `309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8`

Upstream model: https://github.com/xuebinqin/U-2-Net (Apache-2.0).
The upstream license is included in `../licenses/U-2-Net.txt`.
Preprocessing and output normalization follow rembg's U2netpSession (MIT;
see `../licenses/rembg.txt`). This adapter bounds CPU thread count, verifies the
model checksum, handles constant predictions, and preserves existing alpha.

Weights are fixed bundle assets. Runtime never downloads or trains a model.
