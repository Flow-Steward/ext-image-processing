# Image Processing

Local image actions for Flow Steward workflows. No external provider, API key,
GPU, PyTorch, or model server is needed. Images are read and written using the
host's project-scoped artifact grants. Image data is never sent to an inference API.

## Requirements

This release speaks the host contract `extension_host_v2` with its final
execution scope (`group_id`, `for_each_id`, `step_id`, `step_execution_id`)
and is built on `flowsteward-extension-sdk` 0.4.0. A request with another
contract, a missing scope key, or both a Group and a For each as its owner is
refused (`invalid_host_envelope`) before any image artifact is read or written.
The actions work the same for a step at the root, in a Group or in a For each.
Install it on a Flow Steward Core that speaks this contract; an older Core does
not run it.

Logo: `icon.png` (the Flow Steward wave mark).

## Actions

### Upscale Image (`upscale`)

| Input | Default | Meaning |
| --- | --- | --- |
| `artifact_handle` | required | Image artifact from an earlier workflow step |
| `target_width` | 1920 | Maximum output width in pixels |
| `target_height` | 1080 | Maximum output height in pixels |
| `resize_mode` | `resize` | `resize` fits within bounds; `fit_canvas` returns exactly `target_width` x `target_height` |
| `canvas_color` | `white` | Canvas fill for `fit_canvas`: `white`, `transparent`, or `#RRGGBB` |

Pillow's Lanczos filter resizes proportionally inside the requested bounds.
There is no stretching or cropping. The default `resize` mode does not add
padding. For example:

- 1024 x 1024 into 1480 x 1480 produces 1480 x 1480.
- 1024 x 768 into 1920 x 1080 produces 1440 x 1080.
- 768 x 1024 into 1920 x 1080 produces 810 x 1080.

Use `resize_mode=fit_canvas` for strict marketplace formats. For example,
2048 x 512 into 2048 x 2048 produces a centered 2048 x 512 image on a
2048 x 2048 canvas. With `canvas_color=white`, the padding is white.

Smaller bounds downscale. Dimensions must be positive integers, at most 8192
per side, with at most 16,777,216 pixels in the requested bounding box. Extreme
aspect ratios are rounded to at least one pixel per side.

This is non-generative interpolation: it does not invent texture or recover
detail missing from the source. Moderate enlargement such as 1024 to 1480 is
the intended use case. PNG encoding avoids additional JPEG compression losses;
resampling itself is not mathematically lossless.

### Check Image Size (`check_size`)

| Input | Default | Meaning |
| --- | --- | --- |
| `artifact_handle` | required | Source image artifact |
| `target_width` | 2048 | Target width for workflow decisions |
| `target_height` | 2048 | Target height for workflow decisions |

Returns dimensions and flags such as `exact_match`, `needs_resize`,
`needs_padding`, and `recommended_resize_mode`. This action does not create a
new image artifact.

### Remove Background (`remove_background`)

| Input | Default | Meaning |
| --- | --- | --- |
| `artifact_handle` | required | Source image artifact |
| `keep_existing_transparency` | true | Preserve an already non-opaque image without segmentation |

U2-NetP is bundled as a 4.36 MiB ONNX model and runs on CPU with two inference
threads. No downloads happen at runtime. Its input is 320 x 320; the predicted
alpha mask is resized to the source dimensions. Source colors and dimensions
are preserved, and the predicted mask cannot make existing pixels more opaque.

Existing transparency is a shortcut, not proof that all unwanted background is
gone. Set `keep_existing_transparency: false` to process an image that already
has some transparency but still contains unwanted background. The compact model
is suitable for prominent objects; hair, glass, fine edges and busy backgrounds
may need a stronger model or manual work. It does not provide semantic certainty
that a background is present or absent.

## Independent Workflow Actions

The image-transforming actions are independent. Either can run on its own, and
they can be composed in either order: `upscale -> remove_background` or
`remove_background -> upscale`. `check_size` can run before either of them to
branch the workflow. No fixed pipeline is imposed.

One example of composing them is:

1. Install the archive from the Extensions interface in the intended project.
2. Supply an image artifact from a preceding step.
3. Add **Remove Background**, selecting **Image Processing** and mapping the
   source to `artifact_handle`.
4. Add **Upscale Image**, mapping the previous `image_artifact_handle` to its
   `artifact_handle`, then set `target_width` and `target_height`.
5. Pass the resulting `image_artifact_handle` to the next step and use **Test Run**.

Both actions also return actual `width`, `height`, `original_width`,
`original_height`, `has_transparency`, `processing_method`, and `size_bytes`.
They work independently and require no connection configuration.

## Formats And Limits

- Input: non-animated, 8-bit PNG, JPEG, or WebP; at most 20 MiB and 16 megapixels.
- Output: RGBA PNG, at most 70 MiB. Artifact retention is `run_window`.
- EXIF orientation is applied; source EXIF metadata is not copied to output.
- RGB color profiles are preserved; profiled CMYK JPEGs are converted to sRGB.
- Each action processes one image. Use the workflow's iteration controls for batches.
- Invocation timeout: 120 seconds; each artifact transfer timeout: 10 seconds.
- The archive includes CPU wheels for Linux x86-64, CPython 3.12, glibc >= 2.28,
  matching the current Flow Steward container. Other targets need their own wheel lock.

## Resource Checks

Measurements on a synthetic 1024 x 1024 image in the development container:
Lanczos resize plus PNG encoding to 1480 x 1480 took approximately 0.10 seconds
and 40 MiB peak RSS. Background removal with a cold CPU session used roughly
320 MiB peak RSS. These are sample measurements, not production limits or
quality benchmarks. Larger images and concurrent jobs consume more memory;
start with one image job at a time on a small server.

## Development

Dependencies are fully pinned with SHA-256 wheel hashes in `extension.yaml`.
`requirements.in` records the three direct requirements. The host installs
bundled wheels offline in the extension's own environment. The SDK comes from
the host; this extension does not import application internals at runtime.

With the extension dependencies, pytest, PyYAML, and platform dependencies available:

```bash
PYTHONPATH=.:core/infrastructure/extension_sdk/public python -m pytest \
  -c extensions/com_image_processing/pyproject.toml \
  extensions/com_image_processing/tests -x -q
```

The tests cover real CPU inference, artifact I/O, dimensions, alpha preservation,
malformed/animated input, model checksums, dependency closure, and host contract
compilation. Tests use temporary files; no external provider is contacted.

Build with the standard `flow-steward extensions bundle com.image.processing`
command. The package is a Python subprocess extension, not a native executable.

References: [Pillow](https://pillow.readthedocs.io/en/stable/),
[ONNX Runtime](https://onnxruntime.ai/docs/api/python/api_summary.html),
[U-2-Net](https://github.com/xuebinqin/U-2-Net),
[rembg normalization](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2netp.py).
Model provenance and bundled third-party notices are in `models/README.md` and
`licenses/`. Wheel archives retain their upstream license files.
