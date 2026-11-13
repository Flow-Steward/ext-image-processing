# Workflow actions

No connection or API key is needed. Supply a single, non-animated PNG, JPEG or WebP workflow artifact, at most 20 MiB and 16 megapixels. Processing runs locally with the bundled model and image libraries.

Use Inspect image dimensions to branch on needs_resize or needs_padding. To make a square catalog image, choose Resize an image or fit it to a canvas, set width and height to 2048, choose fit_canvas and white. Remove an image background returns a transparent PNG for later steps.

Select the named action in an Extension tools step. Map workflow values to its inputs and map the returned fields needed by later steps. Examples below contain sample data; replace artifact handles and embedding values with actual earlier-step outputs.

## Resize an image or fit it to a canvas

Resize an image proportionally within pixel bounds using Lanczos interpolation, or center it on an exact-size canvas. Returns a PNG artifact without stretching or cropping; smaller bounds reduce the image and enlargement does not recover missing detail.

- **Source image artifact**: Map a single, non-animated PNG, JPEG or WebP artifact from an earlier step. Maximum 20 MiB and 16 megapixels.
- **Target width (pixels)**: Positive integer from 1 to 8192; default 1920. The requested bounding box must not exceed 16777216 pixels. Aspect ratio is preserved.
- **Target height (pixels)**: Positive integer from 1 to 8192; default 1080. The requested bounding box must not exceed 16777216 pixels. Aspect ratio is preserved.
- **Resize or canvas mode**: resize (default) fits inside the bounds without padding. fit_canvas centers the resized image on an exact-size canvas using Canvas color; neither mode stretches or crops.
- **Canvas color**: Used only with fit_canvas. Enter white (default), transparent or a hexadecimal #RRGGBB color.

Example input values:

```json
{
  "target_width": 2048,
  "target_height": 2048,
  "canvas_color": "white",
  "resize_mode": "fit_canvas"
}
```

## Remove an image background

Use the bundled U2-NetP CPU model to create a transparent PNG at the source dimensions. Existing transparency can be preserved without running segmentation; inspect difficult edges before use.

- **Source image artifact**: Map a single, non-animated PNG, JPEG or WebP artifact from an earlier step. Maximum 20 MiB and 16 megapixels.
- **Preserve existing transparency without segmentation**: Default: true. If the source already has non-opaque pixels, return it without background segmentation. Disable to process an image that still has unwanted background despite existing transparency.

Uses the selected project connection; no additional action inputs.

## Inspect image dimensions

Read an image artifact and compare it with target dimensions. Returns dimensions and resize/padding flags for workflow branching without creating a new image.

- **Source image artifact**: Map a single, non-animated PNG, JPEG or WebP artifact from an earlier step. Maximum 20 MiB and 16 megapixels.
- **Target width (pixels)**: Positive integer from 1 to 8192; default 2048. Used only for size comparison; this action does not resize the image.
- **Target height (pixels)**: Positive integer from 1 to 8192; default 2048. Used only for size comparison; this action does not resize the image.

Example input values:

```json
{
  "target_width": 2048,
  "target_height": 2048
}
```
