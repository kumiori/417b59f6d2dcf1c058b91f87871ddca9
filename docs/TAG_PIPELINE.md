# HUBE: video gestures in the terminal

`hube_tag` implements the attached reconstruction brief under HUBE naming. It
recovers timestamped polylines from progressive paint evidence; the terminal
renderer consumes those polylines independently. This is an experimental inverse
pipeline, with explicit uncertainty at intersections and occlusions.

The development workflow is blind: source video, extracted images, and generated
art are not opened or displayed. The supplied photograph was already attached in
the conversation; it supplies the fixed coordinate canvas and final-colour
constraint. Only
repeated registered video observations can add foreground or arrival times.
Numerical success does **not** establish perceptual fidelity.

## Install

Python 3.11+ is required. Rendering and playback use only the standard library.
Offline extraction needs `ffprobe` on PATH (from FFmpeg), and the `vision` extra:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[vision,test]'
# macOS, if FFmpeg is absent:
brew install ffmpeg
```

For the exact tested vision/test versions on Python 3.13, use
`pip install -r requirements-tag.lock`; the portable minimum versions remain in
`pyproject.toml`. The project installs the standalone Game-Gamer 0.2.0 core from
GitHub, pinned to commit `439473d6ee94e59d7c0c29ba16ccbbc915c8fb97`.
Git must be on PATH during installation. No Commons package or sibling checkout
is needed. The lock file covers vision/test libraries; the pinned core dependency
is declared in `pyproject.toml` and installed by `pip install -e '.[vision,test]'`.
To run from this checkout without installing console scripts, replace `hube-tag`
with `.venv/bin/python -m hube_tag`.

## Commands

Use a fresh build directory. `build` refuses an existing frames manifest to avoid
mixing outputs from different sources or settings.

```sh
# Required first: all eight known drawing videos, no images displayed.
hube-tag synthetic --output /tmp/hube-tag-benchmark

hube-tag build 'assets/INPUT.mp4' --output output/tag \
  --reference-photo 'assets/REFERENCE.jpg' --sample-hz 25

# Independent stages; same build root by default:
hube-tag extract 'assets/INPUT.mp4' --output output/tag --sample-hz 25
hube-tag segment output/tag/frames/ --strategy combined --persistence 3
hube-tag reconstruct output/tag/masks/ --pen-up-gap 0.6
hube-tag validate output/tag

# Save art for later human evaluation without displaying it in this workflow:
hube-tag render output/tag/trajectories.json --renderer ascii --output /tmp/tag.txt
hube-tag render output/tag/trajectories.json --renderer unicode --output /tmp/tag-unicode.txt
hube-tag render output/tag/trajectories.json --renderer braille --output /tmp/tag-braille.txt

# These two commands are for the human viewer:
hube-tag animate output/tag/trajectories.json --renderer braille --columns 100
hube-tag play output/tag/trajectories.json --renderer braille --duration 8
hube-tag play output/tag/trajectories.json --timing stylized --duration 6

# Invoke from the existing game:
python3 -m game play hube-stop-01 --splash output/tag/trajectories.json
```

`animate` leaves the completed frame; `play` additionally waits for Enter on an
interactive terminal. Pipes receive one final frame, with no ANSI escapes or wait.
Ctrl-C restores the cursor and returns exit status 130. Game splash playback
happens before creating/opening the game's database. It is opt-in while the
reconstruction still needs human acceptance.

All commands support `--help`. Common options:

| Stage | Options |
| --- | --- |
| extract, build | `--sample-hz 12.5`, `--max-dimension 640` |
| segment, build | `--strategy combined\|color\|temporal`, `--persistence 3`, `--registration-tolerance 2`, `--ink light\|dark`, `--color R G B`, `--tolerance 45`, `--roi X0 Y0 X1 Y1` |
| reconstruct, build | `--pen-up-gap 0.6` (seconds) |
| render, animate, play | `--renderer ascii\|unicode\|braille`, `--columns 100`, `--rows 32`, `--cell-aspect-ratio 0.5`, `--stroke-thickness 1`, `--fit tag\|reference` |
| render | `--timestamp SECONDS`, `--output FILE` |
| animate, play | `--duration SECONDS`, `--fps 30` (maximum 120), `--timing original\|stylized` |

ROI coordinates are normalized to the processed reference frame. Automatic colour
selection estimates lightness from image quantiles with a Lab chroma constraint;
explicit RGB/Lab-distance segmentation is preferable for coloured ink. Do not
choose parameters by looking at images during blind validation.

## Five stage contracts

1. **`video.extract(video, directory)`** → `frames.json`, `frames/*.png`,
   `registered/*.png` and validity masks. FFprobe supplies original per-frame
   presentation timestamps. Base sampling follows elapsed timestamps; significant
   changes and the final frame are additionally retained. Frame-to-frame changes,
   stationary flags, ORB/RANSAC homographies with SIFT fallback, inlier counts, raw and
   exposure-normalized median registration residuals, and validity fractions are
   stored per frame. Reference descriptors are cached. Strong geometric matches
   can enable robust per-channel exposure normalization; its gains/offsets and
   residuals are serialized. With a supplied photograph, SIFT matches select the latest photo-supported
   video frame for provenance, avoiding the unsupported tail. The photograph itself
   supplies the fixed canvas so a zoomed video frame cannot crop the composition.
   Otherwise the reference is the
   latest stationary frame in the last half-second, or the last frame. Missing,
   nonmonotone, or undecodable presentation timestamps fail rather than being
   replaced by assumed uniform spacing. Non-video streams are excluded.
2. **`segmentation.segment(frames_manifest)`** → cumulative `masks/*.png`,
   `birth_times.npy`, `segmentation.json`. Three interchangeable strategies share
   persistence and component checks. Combined is the default: final-colour support,
   change from the registered baseline, and repeated observations of matching
   final colour. Temporal mode drops the colour-class constraint; colour mode drops
   the deposition constraint and explicitly warns about existing marks. A configurable
   two-pixel registration tolerance expands observation support before intersecting
   the final candidate mask. Persistent components below eight pixels are excluded.
   These choices can shift arrival estimates and cannot establish missing pen contact.
   Unreliable
   registration observations are excluded. Per-frame observed disappearance is
   reported independently of the monotonically accumulated persistent foreground.
3. **`trajectories.reconstruct(segmentation_manifest)`** → `trajectories.json`.
   Skeleton pixels form a graph; nearby junctions are contracted into regions.
   Opposing tangents and arrival times propose port pairings. Ordered chains are
   oriented using time evidence, closed loops start near their earliest observed
   front, and isotonic regression fits monotone arrival times. Large time gaps
   split paths; spatially adjacent fragments with compatible timestamps can join.
   Every intersection pairing/join is marked uncertain. Geometry is retained as
   dense polylines, avoiding smoothing that would erase loops or sharp corners.
4. **`raster.render(trajectories, ...)`** → rectangular `list[str]`. The common
   intermediate is a 2×4 subpixel grid per terminal cell. Segments are sampled at
   subpixel resolution and stamped with physical stroke widths. A configurable
   width/height cell ratio and the source image dimensions preserve proportions.
   Braille encodes all eight dots; ASCII and Unicode estimate local orientation
   from the same raster. Cubic Bézier input uses adaptive de Casteljau subdivision.
5. **`animation.animate(trajectories, ...)`** → terminal output. Source point
   times interpolate the deposition front. Original timing keeps measured relative
   timing; an optional duration uniformly scales the playback. Stylized timing
   applies an ease-in/out display-time map, retaining order, pauses, and the source
   data. Changed rows redraw in a reserved region; the whole terminal is not cleared.
   Terminal dimensions are remeasured during playback. Cursor restoration uses
   `finally`, including interruption. The completed frame remains visible.

All JSON has `schema_version: 1`. Image paths are relative to the owning manifest; `reference.png` stores the
fixed canvas. With a photograph, each homography maps video pixels into that
photo canvas and `photo_original_to_reference` stores its scaling separately;
frame IDs are sequential in the selected-frame manifest. `birth_times.npy` is a
plain NumPy float array of source seconds (`-1` = not observed), loadable with
`np.load(path, allow_pickle=False)`. BGR is used internally by OpenCV; CLI colour
values are RGB. Homographies map each resized source frame to the reference.
The video original-to-processed and reference-pixel-to-normalized transforms are
serialized. The canvas can have different dimensions from the decoded video.

For segmentation refinements without decoding again,
`hube_tag.pipeline.process_extracted(directory, reference_photo=photo_path)`
regenerates masks, trajectories, diagnostics and all text exports from the saved
registered frames. It replaces those generated artifacts in that directory.

Each stage can write to a separate directory with `--output`. When doing so, pass
the previous stage's explicit manifest path, rather than relying on sibling names.
`validate` and the end-to-end build use a common root containing all manifests.

## Trajectory contract and reusable API

```json
{
  "schema_version": 1,
  "coordinate_system": "normalized",
  "reference_size": [360, 450],
  "strokes": [{
    "id": "stroke_001",
    "kind": "polyline",
    "t_start": 1.2,
    "t_end": 2.8,
    "direction": "forward",
    "points": [[0.1, 0.4], [0.2, 0.5], [0.4, 0.6]],
    "point_times": [1.2, 1.4, 2.8],
    "width": 0.012,
    "confidence": 0.6,
    "uncertainty": []
  }]
}
```

X and Y are fractions of reference width and height respectively, with the origin
at top left; width is a fraction of reference **width**. `point_times` are source
seconds and carry nonuniform velocity. A forward direction is inferred only when
a time span and sufficient rank correlation support it. `direction: unknown`
means that serialization order is a convention, not recovered gesture direction.
The playback of such a stroke is a candidate interpretation, not established history.
Confidence is a heuristic score, **not** a calibrated probability.

For authored synthetic cubic curves use `kind: bezier` and four `control_points`;
without `point_times`, arc length distributes time along a curve. Reconstructed
strokes always use explicit sampled points/times. No game-specific state enters
this format or the rendering package.

```python
from hube_tag import render, splash
from hube_tag.io import read_json

curves = read_json('output/tag/trajectories.json')
lines = render(curves, renderer='braille', columns=100, rows=32)
splash(curves, duration=6, renderer='braille', prompt='> PRESS ENTER')
```

## Validation and artifacts

Run `python -m pytest tests/tag -q` after installing vision/test dependencies.
Without vision packages, pure rendering tests run and offline tests are skipped.
The eight generated MJPG videos cover line, circle, figure-eight, two intersecting
strokes, an open self-intersecting gesture, pen-up intervals, moving camera, and
temporary occlusion. They contain known nonlinear velocity and an existing bright
background mark that must not be recovered as newly deposited ink.

Synthetic gates use source pixels and seconds: symmetric centreline Chamfer <1.5
px, Hausdorff ≤3.5 px, arrival-time MAE <0.15 s, local direction accuracy ≥90%,
correct gesture count, and no stroke-order inversions. Nearest-geometry time/direction
scores are themselves ambiguous near intersections. The camera test compares in
the final reference coordinate system; its uncorrected source-space score includes
the final camera offset. A separate known-transform test verifies registration.

Tests also cover nonuniform video timestamps, static footage with no deposition,
reproducible artifacts across two fresh builds, independent stage CLIs, Braille bit
mapping, aspect ratio, progressive occupancy, CV-free playback, and cursor cleanup.
Existing game tests verify that the added opt-in splash does not change game rules.

A build produces:

```text
output/tag/
  reference.png         # fixed video/photo coordinate canvas
  frames.json           # PTS, changes, camera transforms and source hash
  segmentation.json     # observed/persistent counts, widths, disappearance
  birth_times.npy       # earliest repeated deposition evidence
  trajectories.json     # standalone curves, timing and uncertainty
  diagnostics.json      # geometry, temporal, registration and raster metrics
  run.json              # elapsed time, process peak RSS, dependency versions
  final_ascii.txt
  final_unicode.txt
  final_braille.txt
  frames/ registered/ masks/   # PNG diagnostics for later human evaluation
```

Outputs are deterministic for the same asset/configuration/dependency versions;
`run.json` is intentionally excluded from byte comparisons because timing and
process high-water memory vary. OpenCV uses one thread and a fixed RNG seed.
PNG directories and generated videos are ignored by Git to avoid large accidental
adds; they remain on disk. Keep manifests, curves, numerical reports, and versions
with any released splash. Runtime is proportional to decoded frames and image
area. Memory uses the current/reference frames and arrival maps rather than a
whole-video tensor; `run.json` reports measured process lifetime peak RSS.

## Limits requiring human or additional evidence

- Existing same-colour background marks, highlights, paper texture, and reflections
  can survive colour segmentation. Combined segmentation reduces them but cannot
  prove semantic separation of paint, hand, and tool. There is no trained hand model.
- Without a photograph, the selected final frame must contain the completed tag. Without a useful photo match, an end card, cut, strong
  perspective change, rolling shutter, nonplanar motion, or poor texture can defeat
  registration/reference selection. Residual and reliability checks expose risk;
  they are not a scene-understanding model or a guaranteed shot-cut detector.
- Completely hidden deposition, retracing already identical ink, and sub-frame pen
  lifts are unobservable. Do not treat a graph traversal as unique physical history.
  Junction contraction and short cap joins can lose or merge nearby fine decoration.
- Occlusion can delay birth estimates; isotonic time fitting is reported per stroke.
  A pen held still cannot be distinguished reliably from a pen lifted and returned.
- Colour candidate gating excludes strokes on existing ink of the same colour and
  may lose portions against bright backgrounds. The photo constrains colour and coordinates; paint is retained only where
  repeated registered video observations support it. No gesture order or timing
  is inferred from the photograph alone.
- Raster error, topology, and aspect scores measure the common subpixel grid.
  ASCII/Unicode glyph appearance depends on the font and is not measured by those
  metrics. Braille normally offers the most faithful occupancy representation.
- Small terminal grids can merge fine strokes. Resizing and ambiguous gesture
  playback still need later human review in the target terminal emulator.

See [TAG_EVALUATION.md](TAG_EVALUATION.md) for measured results and remaining
acceptance limits on the supplied assets.
