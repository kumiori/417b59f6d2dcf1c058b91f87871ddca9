"""Offline orchestration; each stage can also be run independently."""
from pathlib import Path
import platform
import resource
import time
from .io import write_json, read_json


def build(source, output, *, sample_hz=12.5, max_dimension=640, strategy='combined',
          persistence=3, ink='light', color=None, tolerance=45, roi=None,
          pen_up_gap=0.6, reference_photo=None, registration_tolerance=2):
    from .video import extract
    root = Path(output)
    if (root/'frames.json').exists():
        raise ValueError(f'output already contains a build: {root}; use a fresh directory')
    began = time.perf_counter()
    extract(source,root,sample_hz=sample_hz,max_dimension=max_dimension,reference_photo=reference_photo)
    elapsed = time.perf_counter()-began
    return process_extracted(root,strategy=strategy,persistence=persistence,ink=ink,
        color=color,tolerance=tolerance,roi=roi,pen_up_gap=pen_up_gap,
        reference_photo=reference_photo,registration_tolerance=registration_tolerance,
        extraction_seconds=elapsed)


def process_extracted(output, *, strategy='combined', persistence=3, ink='light',
                      color=None, tolerance=45, roi=None, pen_up_gap=0.6,
                      reference_photo=None, registration_tolerance=2, extraction_seconds=0):
    """Reprocess an existing registered manifest without decoding the video again.

    Replaces segmentation, curves, diagnostics and exports in the same directory.
    extraction_seconds can retain a previously measured extraction cost in run.json.
    """
    import cv2
    import numpy as np
    import scipy
    import skimage
    from .segmentation import segment
    from .trajectories import reconstruct
    from .diagnostics import evaluate
    from .raster import render
    from .io import sha256
    root = Path(output)
    began = time.perf_counter()
    times = {'extract_seconds':extraction_seconds}
    start = time.perf_counter()
    segment(root/'frames.json',strategy=strategy,persistence=persistence,ink=ink,
            color=color,tolerance=tolerance,roi=roi,registration_tolerance=registration_tolerance)
    times['segment_seconds'] = time.perf_counter()-start
    start = time.perf_counter()
    document = reconstruct(root/'segmentation.json',pen_up_gap=pen_up_gap)
    times['reconstruct_seconds'] = time.perf_counter()-start
    report = evaluate(root,document)
    if reference_photo:
        # Static colour support only; the canvas can itself be this photograph.
        from .segmentation import colour_mask
        from .registration import register
        photo = cv2.imread(str(reference_photo))
        if photo is None:
            raise ValueError('cannot decode reference photograph')
        frames = read_json(root/'frames.json')
        frame = cv2.imread(str(root/frames['reference_path']))
        # Scale only for feature matching; the estimated transform is recorded.
        oh,ow = photo.shape[:2]
        photo = cv2.resize(photo,(frame.shape[1],frame.shape[0]))
        warped,valid,metrics = register(photo,frame)
        observed = cv2.imread(str(root/'masks'/f"mask_{len(frames['frames'])-1:04}.png"),0)>0
        photo_mask = colour_mask(warped,ink=ink,color=color,tolerance=tolerance)&valid
        support = float(photo_mask[observed].mean()) if observed.any() and metrics['reliable'] else None
        report['reference_photo'] = {'source_name':Path(reference_photo).name,'source_sha256':sha256(reference_photo),
            'original_size':[ow,oh],'initial_resize':[frame.shape[1]/ow,frame.shape[0]/oh],
            'registration':metrics,'foreground_colour_support_fraction':support,
            'role':'coordinate canvas and colour constraint only; not independent validation; does not establish stroke direction or timing'}
        write_json(root/'diagnostics.json',report)
    for mode in ('ascii','unicode','braille'):
        # Save without printing: the implementation/validation workflow is blind.
        (root/f'final_{mode}.txt').write_text('\n'.join(render(document,renderer=mode))+'\n',encoding='utf-8')
    times['total_seconds'] = extraction_seconds+time.perf_counter()-began
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write_json(root/'run.json',{'timing':times,
        'process_peak_rss_mib':peak/(1024**2 if platform.system() == 'Darwin' else 1024),
        'memory_scope':'process lifetime high-water mark, not isolated per build',
        'versions':{'python':platform.python_version(),'opencv':cv2.__version__,'numpy':np.__version__,
                    'scipy':scipy.__version__,'scikit_image':skimage.__version__}})
    return report
