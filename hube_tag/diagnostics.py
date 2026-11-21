"""Blind quantitative validation. Metrics are evidence, not perceptual approval."""
from pathlib import Path
import math
import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from .geometry import bounds, samples
from .io import read_json, write_json
from .raster import occupancy, cells
from .skeleton import graph


def distance_metrics(a,b):
    if len(a) == 0 or len(b) == 0:
        return {'chamfer_pixels':None,'hausdorff_pixels':None}
    ab = cKDTree(b).query(a)[0]
    ba = cKDTree(a).query(b)[0]
    return {'chamfer_pixels':float((ab.mean()+ba.mean())/2),
            'hausdorff_pixels':float(max(ab.max(),ba.max()))}


def vector_pixels(document, timestamp=None):
    from .geometry import partial
    w,h = document['reference_size']
    mask = np.zeros((h,w),np.uint8)
    for stroke in document['strokes']:
        points = partial(stroke,timestamp)
        points = np.rint(np.array(points)*[w,h]).astype(np.int32) if points else []
        if len(points) > 1:
            cv2.polylines(mask,[points],False,1,1)
        elif len(points) == 1:
            x,y = points[0]
            mask[min(y,h-1),min(x,w-1)] = 1
    return mask.astype(bool)


def evaluate(root, document=None, *, resolutions=((60,24),(100,32),(140,44))):
    root = Path(root)
    document = document or read_json(root/'trajectories.json')
    segmentation = read_json(root/'segmentation.json')
    frames = read_json(root/'frames.json')
    mask = cv2.imread(str(root/segmentation['final_mask']),0)>0
    center,_,junctions = graph(mask)
    predicted = vector_pixels(document)
    final_error = distance_metrics(np.argwhere(predicted),np.argwhere(center))
    w,h = document['reference_size']
    arcs, velocities, curvature = [],[],[]
    for stroke in document['strokes']:
        points,times = samples(stroke)
        coords = np.array(points)*[w,h]
        lengths = np.linalg.norm(np.diff(coords,axis=0),axis=1)
        arcs.append(float(lengths.sum()))
        for d,dt in zip(lengths,np.diff(times)):
            if dt > 1e-9:
                velocities.append(float(d/dt))
        for a,b in zip(np.diff(coords,axis=0),np.diff(coords,axis=0)[1:]):
            if np.linalg.norm(a)*np.linalg.norm(b) > 0:
                curvature.append(float(math.acos(np.clip(np.dot(a,b)/np.linalg.norm(a)/np.linalg.norm(b),-1,1))))
    box = bounds(document)
    expected_aspect = (box[2]-box[0])*w/max((box[3]-box[1])*h,1)
    raster_metrics = []
    vector_xy = np.argwhere(predicted)[:,::-1]
    for columns,rows in resolutions:
        grid,transform = occupancy(document,columns=columns,rows=rows)
        dots = np.array(grid,dtype=bool)
        ys,xs = np.nonzero(dots)
        physical = np.column_stack(((xs+0.5)*transform['pitch'][0],(ys+0.5)*transform['pitch'][1]))
        back = (physical-transform['offset'])/transform['scale'] + np.array(box[:2])*[w,h]
        _,components = ndi.label(dots,structure=np.ones((3,3)))
        aspect = ((xs.max()-xs.min()+1)*transform['pitch'][0]/((ys.max()-ys.min()+1)*transform['pitch'][1])) if len(xs) else 0
        for mode in ('ascii','unicode','braille'):
            lines = cells(grid,mode)
            raster_metrics.append({'columns':columns,'rows':rows,'renderer':mode,
                'occupancy_ratio':float(dots.mean()), 'connected_components':int(components),
                'aspect_ratio_error':abs(aspect/expected_aspect-1) if expected_aspect else None,
                'raster_to_vector':distance_metrics(back,vector_xy),
                'occupied_cells':sum(c != ' ' for line in lines for c in line),
                'metric_scope':'common subpixel raster; glyph perception not measured'})
    temporal = []
    # Sample evolution rather than validating only the last frame.
    step = max(1,len(segmentation['frames'])//20)
    for f in segmentation['frames'][::step]:
        observed = cv2.imread(str(root/f['path']),0)>0
        observed_center,_,_ = graph(observed)
        temporal.append({'timestamp':f['timestamp'],**distance_metrics(np.argwhere(vector_pixels(document,f['timestamp'])),np.argwhere(observed_center))})
    durations = [s['t_end']-s['t_start'] for s in document['strokes']]
    last_end = -1
    pen_ups = 0
    for stroke in document['strokes']:
        if last_end >= 0 and stroke['t_start'] > last_end+document['reconstruction']['time_resolution_seconds']:
            pen_ups += 1
        last_end = max(last_end,stroke['t_end'])
    quantiles = lambda v: np.quantile(v,[0.1,0.5,0.9]).tolist() if len(v) else []
    warnings = list(document['warnings'])
    if any(s['uncertainty'] for s in document['strokes']):
        warnings.append('Inspect per-stroke uncertainty before treating these trails as original gestures.')
    report = {'schema_version':1,'visual_inspection_performed':False,
        'acceptance':'numerical diagnostics only; perceptual fidelity and ambiguous gestures require later human evaluation',
        'geometry':{'stroke_count':len(document['strokes']),'total_length_pixels':sum(arcs),
            'intersection_regions_observed':junctions,'intersection_regions_reconstructed':graph(predicted)[2],
            'bounding_box_normalized':box,'bounding_box_aspect':expected_aspect,
            'curvature_turn_radians_quantiles':quantiles(curvature),**final_error},
        'temporal':{'durations_seconds':durations,'velocity_pixels_per_second_quantiles':quantiles(velocities),
            'pen_up_intervals':pen_ups,'start_order_consistent':all(a['t_start']<=b['t_start'] for a,b in zip(document['strokes'],document['strokes'][1:])),
            'observable_direction_fraction':sum(s['direction']!='unknown' for s in document['strokes'])/max(1,len(document['strokes'])),
            'mean_confidence':float(np.mean([s['confidence'] for s in document['strokes']])) if document['strokes'] else 0,
            'evolution_error':temporal},
        'segmentation':{'persistent_foreground_pixels':int(mask.sum()),
            'persistent_deposition_fraction':segmentation['persistent_deposition_fraction'],
            'unexpected_decreases':sum(f['unexpected_decrease'] for f in segmentation['frames']),
            'foreground_monotone':all(a['foreground_pixels']<=b['foreground_pixels'] for a,b in zip(segmentation['frames'],segmentation['frames'][1:])),
            'final_components':segmentation['frames'][-1]['connected_components'],
            'width_pixels_quantiles':segmentation['frames'][-1]['width_quantiles']},
        'video':{'reference_canvas':frames['reference_canvas'], 'reference_frame_id':frames['reference_frame_id'],
            'reference_timestamp':frames['frames'][frames['reference_frame_id']]['timestamp'],
            'reference_selection':frames['reference_selection'],
            'duration':frames['duration'],'decoded_frames':frames['decoded_frames'],'selected_frames':len(frames['frames']),
            'sample_hz':frames['sample_hz'],'stationary_frames':sum(f['stationary'] for f in frames['frames']),
            'registration_unreliable_frames':sum(not f['reliable'] for f in frames['frames']),
            'registration_residual_quantiles':quantiles([f['registration_residual'] for f in frames['frames']]),
            'camera_motion_pixels_quantiles':quantiles([f['camera_motion_pixels'] for f in frames['frames']]),
            'drawing_intervals':[[f['timestamp'],f['new_pixels']] for f in segmentation['frames'] if f['new_pixels']]},
        'rasterization':raster_metrics,'warnings':warnings}
    write_json(root/'diagnostics.json',report)
    return report
