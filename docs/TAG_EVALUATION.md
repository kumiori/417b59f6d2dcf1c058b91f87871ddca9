# HUBE tag reconstruction: measured evaluation

The pipeline and terminal integration are implemented and exercised. The real
asset output is an **experimental candidate**, not a visually accepted logo or an
exact reconstruction of the artist's gestures. Development used numerical and
structural diagnostics without opening source frames or rendered art.

**Real-tag acceptance remains unmet.** The supplied footage produces fragmented
segmentation, many uncertain trails, and a large worst-case reconstruction error.
The splash stays opt-in. All 82 automated tests pass; this does not override that
real-asset limitation.

## Synthetic ground truth

Eight mandatory known videos were generated and tested before real reconstruction.
The fixtures include nonlinear drawing velocity, existing background paint, camera
motion, temporary occlusion, pen-up gaps, closed loops, and crossings.

| Case | Chamfer (px) | Hausdorff (px) | Time MAE (s) | Local direction | Stroke-count error |
| --- | ---: | ---: | ---: | ---: | ---: |
| camera_motion | 1.135 | 2.000 | 0.064 | 100.0% | 0 |
| circle | 0.195 | 1.000 | 0.085 | 96.8% | 0 |
| figure_eight | 0.183 | 1.000 | 0.052 | 97.5% | 0 |
| intersecting | 0.135 | 1.414 | 0.053 | 96.2% | 0 |
| line | 0.095 | 1.000 | 0.049 | 100.0% | 0 |
| occlusion | 0.095 | 1.000 | 0.075 | 100.0% | 0 |
| pen_up | 0.167 | 1.414 | 0.057 | 100.0% | 0 |
| self_intersecting | 0.236 | 3.000 | 0.051 | 93.9% | 0 |

All eight satisfy the stated numerical gates (Chamfer <1.5 px, Hausdorff ≤3.5 px,
time MAE <0.15 s, direction ≥90%, exact gesture counts, zero ordering inversions).
The camera-motion score includes the final reference offset. Crossings and
short-fragment joins remain marked ambiguous even when the synthetic count is
correct. Nearest-geometry timing/direction scores are ambiguous at intersections.
The saved benchmark is `output/synthetic/benchmark.json`; fixture generation
is reproducible with `python -m hube_tag synthetic --output NEW_DIRECTORY`.

## Supplied video and photograph

- Video: `+ NHMI LIMITED 200 GRAMS POSTER + 🚨🚫🚨- Poster 50x70 - Carta 200 grammi- Tiratura Limitata- Us.mp4`.
- Source SHA-256: `117772176e98bd4d4af2d390b94d1734a33b6232b8f84c0fe043e628eef6d598`.
- Photograph SHA-256: `f02bed881b1ef0680be224f34255e193472c29c32f6efe1fefbdec682ce7a8a0`.
- Duration: 24.28 s; decoded/selected frames:
  607/607; requested sampling: 25.0 Hz.
- Video dimensions: [360, 450]; fixed photo canvas:
  [512, 640] (normalized coordinates retain those proportions).
- Latest photograph-supported video frame: #565,
  22.60 s. The final
  1.64 s do not pass that
  matching criterion. This is a numerical scene-change indication, not visual classification.
- Reliable frame registrations: 561/607.
- Raw registration residuals, 10th/50th/90th percentiles:
  35.00, 36.00, 40.00 gray levels on reliable frames.
- Exposure-normalized residuals, same percentiles:
  16.00, 19.00, 28.00 gray levels.

Early attempts using the final video frame failed to align most frames. Matching
against the supplied photograph indicated a change in matchable content. A later video canvas
also cropped the drawing because its estimated field of view is narrower. The final build uses the whole
photograph as the coordinate canvas, registers video frames onto it, and normalizes
exposure only when supported by a strong feature match. The photo supplies colour
and coordinates, never pen trajectories or arrival times. A pixel enters the mask
only after repeated compatible video observations. The baseline must register
reliably; otherwise deposition inference is refused.

## Real reconstruction evidence and uncertainty

- Persistent foreground: 11203 pixels;
  final connected components: 63.
- Candidate graph trails: 111; total curve length:
  2104.47 source-canvas pixels.
- Observed/reconstructed skeleton junction regions:
  87/13.
  Regions are a topology diagnostic, not a count of physical pen crossings.
- Direction supported by arrival-time variation/correlation:
  39/111 trails. The remainder retain `direction: unknown`.
- Trails with at least one uncertainty: 97/111.
- Mean heuristic confidence: 0.203; this is not
  a calibrated probability.
- Vector-to-observed-final-centreline symmetric Chamfer:
  0.416 px; Hausdorff: 55.660 px.
  These are **self-consistency errors against segmentation**, not errors against
  independent ground truth of the tag. They cannot validate missed or false paint.
- Persistent area is monotone: True.
  Significant observed disappearances: 130;
  they can reflect occlusion, registration, or lighting and are retained in diagnostics.

A numerical colour-component check found 2,514 already-light baseline pixels
in a 14,003-pixel final component, of which 9,270 pixels have persistent new-mark
support. This is evidence of incomplete temporal identifiability, not proof that
all baseline light pixels were pre-existing tag paint. The two-pixel registration
tolerance and an eight-pixel persistent-component filter reduce fragmentation;
they do not recover hidden gestures or establish semantic paint isolation.

Reported trail uncertainties:

- 85 trails: Large arrival gap split this path; a stationary pen and pen-up cannot be distinguished.
- 72 trails: Direction unobservable at available temporal resolution; polyline orientation is only a serialization convention.
- 55 trails: Arrival times conflict with traversal; occlusion, registration, or pairing may explain the residual.
- 20 trails: Intersection continuation chosen by time and tangent; alternative pairings may exist.
- 1 trail: Foreground already present in first observations; pen-down and direction may predate the video.

Inspect `output/tag/trajectories.json` for each trail's interval, sampled velocity,
confidence, and uncertainty; `diagnostics.json` also contains temporal evolution
errors. Unknown direction is played using a serialization convention. Intersections,
pen lifts, stationary gestures, and identical-ink retracing are not uniquely
recoverable from these observations. No claim of original stroke count, complete
paint isolation, or exact timing is made for the real asset.

## Terminal fidelity

All three character modes consume the same subpixel raster. These measurements
apply to that raster, not font-specific ASCII/Unicode glyph appearance.

| Grid | Occupancy | Components | Aspect error | Raster→vector Chamfer (source px) |
| --- | ---: | ---: | ---: | ---: |
| 60×24 | 5.01% | 27 | 1.49% | 1.73 |
| 100×32 | 3.72% | 34 | 0.35% | 1.44 |
| 140×44 | 3.54% | 37 | 0.65% | 1.21 |

The final ASCII, Unicode, and Braille text buffers are saved in `output/tag/`.
They have not been visually inspected. Numerical agreement cannot establish
perceptual fidelity. A later human review in the target terminal is still required
before enabling this candidate as the default game splash.

## Runtime and reproduction

The registered extraction was reused for the final segmentation refinement.
The following total combines its measured extraction cost with the final
segmentation/reconstruction/export pass; it is not one uninterrupted wall-clock run.

Final build time: 197.19 s; extraction/registration:
149.14 s; segmentation:
47.24 s; reconstruction:
0.14 s. Process lifetime peak RSS:
314.44 MiB for the separate refinement process. The earlier full extraction
and strict-segmentation process measured 392.31 MiB. These are observed high-water
marks, not guaranteed memory bounds. Measurements depend on hardware and concurrent
work; peak RSS is not a per-stage allocation measurement. Image files are streamed
rather than retained as a dense whole-video tensor. Full PNG diagnostics remain
on disk and are ignored by Git.

Versions: numpy 2.5.4, opencv 5.0.0, python 3.13.3, scikit_image 0.26.0, scipy 1.18.1.
`requirements-tag.lock` pins the tested vision/test environment. Reproducibility
tests compare all scientific manifests, curves, arrival maps, and text buffers
byte-for-byte across two fresh builds; wall time and memory are excluded.

```sh
.venv/bin/hube-tag build 'assets/+ NHMI LIMITED 200 GRAMS POSTER + 🚨🚫🚨- Poster 50x70 - Carta 200 grammi- Tiratura Limitata- Us.mp4' \
  --reference-photo 'assets/+ NHMI LIMITED 200 GRAMS POSTER + 🚨🚫🚨- Poster 50x70 - Carta 200 grammi- Tiratura Limitata- Us.jpg' \
  --sample-hz 25 --persistence 3 --output /tmp/hube-tag-reproduction

.venv/bin/hube-tag play output/tag/trajectories.json --renderer braille --duration 8
.venv/bin/game play hube-stop-01 --splash output/tag/trajectories.json
```

Playback imports no CV dependencies. The game integration is opt-in and does not
change its world, identity, transactions, or saved-state rules. Installation and
stage contracts are documented in `docs/TAG_PIPELINE.md`.

## Remaining real-asset acceptance work

Paint isolation and temporal continuity need to improve before this can serve as
the accepted HUBE logo. A fixed-camera recording with an initially unmarked, fully
visible surface would provide stronger deposition evidence. With this clip, any
further method must validate hand/occlusion handling and component selection
against independent evidence, then receive human perceptual review. The current
low average centreline error is insufficient to accept the candidate.
