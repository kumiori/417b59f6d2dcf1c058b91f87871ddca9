"""Stage 3: persistent masks + birth map -> normalized timed polylines."""
from pathlib import Path
import math
import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.stats import spearmanr
from .io import read_json, write_json
from .skeleton import graph, trails, isotonic


def reconstruct(manifest, output=None, *, pen_up_gap=0.6, minimum_length=4):
    path = Path(manifest)
    if path.is_dir():
        path = path/'segmentation.json' if (path/'segmentation.json').exists() else path.parent/'segmentation.json'
    if not math.isfinite(pen_up_gap) or pen_up_gap <= 0:
        raise ValueError('pen_up_gap must be finite and positive')
    document = read_json(path)
    root = path.parent
    output = Path(output) if output else root
    mask = cv2.imread(str(root/document['final_mask']),0)
    if mask is None:
        raise ValueError('missing final segmentation mask')
    mask = mask > 0
    birth = np.load(root/document['birth_times'],allow_pickle=False)
    h,w = mask.shape
    center,adjacency,junctions = graph(mask)
    widths = ndi.distance_transform_edt(mask)*2
    stamps = [f['timestamp'] for f in document['frames']]
    dt = float(np.median(np.diff(stamps))) if len(stamps) > 1 else 1
    paths = trails(adjacency,birth,time_scale=dt*3)
    strokes = []
    rejected = 0
    for path_pixels in paths:
        arc = sum(math.dist(a,b) for a,b in zip(path_pixels,path_pixels[1:]))
        if arc < minimum_length and len(path_pixels) > 1:
            rejected += 1
            continue
        values = [float(birth[p]) for p in path_pixels]
        valid = [v for v in values if v >= 0]
        if not valid:
            continue
        values = [v if v >= 0 else min(valid) for v in values]
        correlation = float(spearmanr(np.arange(len(values)),values).statistic) if len(set(values)) > 1 and len(values)>2 else 0
        if not math.isfinite(correlation):
            correlation = 0
        if correlation < 0:
            path_pixels.reverse()
            values.reverse()
        # Isotonic regression repairs early arrival times at self-intersections.
        fitted = isotonic(values)
        residual = float(np.sqrt(np.mean((np.array(values)-np.array(fitted))**2)))
        splits = [0]+[i for i in range(1,len(fitted)) if fitted[i]-fitted[i-1] > pen_up_gap]+[len(fitted)]
        for first,last in zip(splits,splits[1:]):
            pixels = path_pixels[first:last]
            times = fitted[first:last]
            if not pixels:
                continue
            uncertainty = []
            spread = max(times)-min(times)
            direction_known = spread >= dt*0.5 and abs(correlation) >= 0.2
            if not direction_known:
                uncertainty.append('Direction unobservable at available temporal resolution; polyline orientation is only a serialization convention.')
            if any(len(adjacency[p]) > 2 for p in pixels):
                uncertainty.append('Intersection continuation chosen by time and tangent; alternative pairings may exist.')
            if min(times) <= stamps[0]+dt:
                uncertainty.append('Foreground already present in first observations; pen-down and direction may predate the video.')
            if residual > dt*2:
                uncertainty.append('Arrival times conflict with traversal; occlusion, registration, or pairing may explain the residual.')
            if len(splits) > 2:
                uncertainty.append('Large arrival gap split this path; a stationary pen and pen-up cannot be distinguished.')
            confidence = (0.85 if direction_known else 0.25)*math.exp(-residual/max(dt*3,0.001))
            if uncertainty:
                confidence *= 0.75
            strokes.append({'id':'', 'kind':'polyline', 't_start':float(min(times)),
                't_end':float(max(times)), 'direction':'forward' if direction_known else 'unknown',
                'points':[[float(x/w),float(y/h)] for y,x in pixels], 'point_times':times,
                'width':float(np.median([widths[p] for p in pixels])/w),
                'confidence':confidence,'temporal_fit_rmse_seconds':residual,
                'uncertainty':uncertainty})
    strokes.sort(key=lambda s:(s['t_start'],s['t_end'],s['points'][0]))
    # Contracted sharp-corner junctions can leave short cap fragments. Join
    # ONLY when both spatial proximity and source-time continuity support it.
    # A pen-up at this resolution remains explicitly ambiguous.
    changed = True
    while changed:
        changed = False
        for i,a in enumerate(strokes):
            candidates = []
            for j,b in enumerate(strokes):
                if i == j or b['t_start'] < a['t_start'] or a['direction'] == 'unknown' or b['direction'] == 'unknown':
                    continue
                gap = b['t_start']-a['t_end']
                distance = math.dist(np.array(a['points'][-1])*[w,h],np.array(b['points'][0])*[w,h])
                if -dt*3 <= gap <= dt*3 and distance <= max(a['width'],b['width'])*w*1.5:
                    candidates.append((distance,j))
            if not candidates:
                continue
            _,j = min(candidates)
            b = strokes[j]
            a['points'] += b['points']
            a['point_times'] = isotonic(a['point_times']+b['point_times'])
            a['t_start'],a['t_end'] = min(a['point_times']),max(a['point_times'])
            a['confidence'] = min(a['confidence'],b['confidence'])*0.8
            a['uncertainty'] = list(dict.fromkeys(a['uncertainty']+b['uncertainty']+[
                'Fragments joined using spatial proximity and compatible arrival times; pen contact between them is unobserved.']))
            strokes.pop(j)
            changed = True
            break
    strokes.sort(key=lambda s:(s['t_start'],s['t_end'],s['points'][0]))
    for i,stroke in enumerate(strokes,1):
        stroke['id'] = f'stroke_{i:03}'
    warnings = list(document['warnings'])
    if junctions:
        warnings.append(f'{junctions} skeleton junction regions require time-guided continuation; exact gesture count is uncertain.')
    result = {'schema_version':1, 'coordinate_system':'normalized', 'reference_size':[w,h],
        'source_sha256':document['source_sha256'],
        'transform':{'original_to_processed':document['original_to_processed'],
                     'reference_canvas':document['reference_canvas'],
                     'photo_original_to_reference':document['photo_original_to_reference'],
                     'pixel_to_normalized':[[1/w,0,0],[0,1/h,0],[0,0,1]]},
        'reconstruction':{'method':'persistent-arrival skeleton graph with temporal/tangent trails',
            'pen_up_gap':pen_up_gap, 'time_resolution_seconds':dt,
            'junction_regions':junctions,'discarded_short_paths':rejected,
            'direction_observable_strokes':sum(s['direction'] != 'unknown' for s in strokes)},
        'warnings':warnings,'strokes':strokes}
    write_json(output/'trajectories.json',result)
    return result
