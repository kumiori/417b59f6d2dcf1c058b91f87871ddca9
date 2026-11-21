"""Stage 2: registered frame manifest -> persistent masks + arrival time map.

Final-frame colour candidates bound persistent paint; consecutive observations
reject transient objects. Temporal mode requires change from the baseline.
The photo is not silently substituted for evidence of deposition.
"""
from pathlib import Path
import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from .io import read_json, write_json, sha256


def colour_mask(image, *, ink='light', color=None, tolerance=45):
    lab = cv2.cvtColor(image,cv2.COLOR_BGR2LAB).astype(float)
    if color is not None:
        target = cv2.cvtColor(np.uint8([[color]]),cv2.COLOR_RGB2LAB)[0,0].astype(float)
        return np.linalg.norm(lab-target,axis=2) < tolerance
    # Adapt the lightness threshold but retain chroma constraints. Explicit RGB
    # overrides are available for coloured ink; automatic mode targets light ink.
    if ink == 'dark':
        threshold = min(70,float(np.percentile(lab[:,:,0],12))+15)
        return (lab[:,:,0] < threshold) & (np.linalg.norm(lab[:,:,1:]-128,axis=2) < 45)
    threshold = max(175,float(np.percentile(lab[:,:,0],85))-25)
    return (lab[:,:,0] > threshold) & (np.linalg.norm(lab[:,:,1:]-128,axis=2) < 40)


def clean(mask, minimum=8):
    labels,count = ndi.label(mask)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= minimum
    keep[0] = False
    return keep[labels]


def segment(manifest, output=None, *, strategy='combined', persistence=3,
            ink='light', color=None, tolerance=45, roi=None, minimum_component=8, registration_tolerance=2):
    if color is not None and (len(color)!=3 or any(not 0<=v<=255 for v in color)):
        raise ValueError('color must contain three RGB values between 0 and 255')
    path = Path(manifest)
    if path.is_dir():
        path = path/'frames.json' if (path/'frames.json').exists() else path.parent/'frames.json'
    frames = read_json(path)
    root = path.parent
    output = Path(output) if output else root
    output.mkdir(parents=True,exist_ok=True)
    (output/'masks').mkdir(exist_ok=True)
    if strategy not in ('color','temporal','combined') or persistence < 1:
        raise ValueError('invalid segmentation strategy or persistence')
    if tolerance <= 0 or minimum_component < 1 or registration_tolerance < 0:
        raise ValueError('tolerance and minimum_component must be positive')
    records = frames['frames']
    if len(records) < persistence:
        raise ValueError('fewer frames than persistence window')
    def load(record):
        image = cv2.imread(str(root/record['registered_path']))
        valid = cv2.imread(str(root/record['valid_path']),0)
        if image is None or valid is None:
            raise ValueError('missing registered frame or validity mask')
        return image, valid > 0
    reference = cv2.imread(str(root/frames['reference_path']))
    if reference is None:
        raise ValueError('missing reference canvas')
    baseline,base_valid = load(records[0])
    h,w = baseline.shape[:2]
    region = np.ones((h,w),bool)
    if roi:
        x0,y0,x1,y1 = roi
        if not 0 <= x0 < x1 <= 1 or not 0 <= y0 < y1 <= 1:
            raise ValueError('ROI must be x0,y0,x1,y1 normalized to the image')
        region[:] = False
        region[round(y0*h):round(y1*h),round(x0*w):round(x1*w)] = True
    final_color = colour_mask(reference,ink=ink,color=color,tolerance=tolerance) & region
    base_color = colour_mask(baseline,ink=ink,color=color,tolerance=tolerance)
    # New paint must be photometrically different from the baseline in temporal
    # strategies; final-colour gating avoids retaining a moving hand forever.
    delta_final = np.linalg.norm(reference.astype(float)-baseline.astype(float),axis=2)
    candidate = final_color.copy() if strategy != 'temporal' else region.copy()
    if strategy in ('combined','temporal'):
        candidate &= (delta_final > 35) & base_valid
        if strategy == 'combined':
            candidate &= ~base_color
    baseline_unreliable = not records[0]['reliable'] and strategy != 'color'
    if baseline_unreliable:
        candidate[:] = False
    candidate = clean(candidate,minimum_component)
    run = np.zeros((h,w),np.uint16)
    birth = np.full((h,w),-1.0)
    persistent = np.zeros((h,w),bool)
    accumulated = np.zeros((h,w),bool)
    metrics = []
    previous_observed = np.zeros((h,w),bool)
    for index,record in enumerate(records):
        image,valid = load(record)
        color_now = colour_mask(image,ink=ink,color=color,tolerance=tolerance)
        difference = np.linalg.norm(image.astype(float)-baseline.astype(float),axis=2) > 35
        evidence = valid.copy()
        if strategy in ('combined','color'):
            evidence &= color_now
        if strategy in ('combined','temporal'):
            evidence &= difference
            # Reject transient changes whose colour differs from the final paint.
            evidence &= np.linalg.norm(image.astype(float)-reference.astype(float),axis=2) < 65
        if registration_tolerance:
            evidence = ndi.binary_dilation(evidence,iterations=registration_tolerance)
        observed = candidate & evidence & valid
        reliable = record['reliable']
        if not reliable:
            observed[:] = False
        run = np.where(observed,run+1,0).astype(np.uint16)
        new = (run >= persistence) & ~accumulated
        if index >= persistence-1:
            birth[new] = records[index-persistence+1]['timestamp']
        lost = previous_observed & ~observed & valid
        accumulated |= new
        previous_persistent = persistent
        persistent = clean(accumulated,minimum_component)
        accepted_new = persistent & ~previous_persistent
        distance = ndi.distance_transform_edt(persistent)
        center = skeletonize(persistent)
        widths = 2*distance[center]
        _,components = ndi.label(persistent)
        confidence = float(observed[persistent].mean()) if persistent.any() else 0
        metrics.append({'frame_id':record['frame_id'],'timestamp':record['timestamp'],
            'foreground_pixels':int(persistent.sum()),'observed_pixels':int(observed.sum()),
            'new_pixels':int(accepted_new.sum()),'disappeared_pixels':int(lost.sum()),
            'unexpected_decrease':bool(lost.sum() > max(10,previous_observed.sum()*0.1)),
            'connected_components':int(components),
            'estimated_stroke_width':float(np.median(widths)) if len(widths) else 0,
            'width_quantiles':np.quantile(widths,[0.1,0.5,0.9]).tolist() if len(widths) else [0,0,0],
            'confidence':confidence,'registration_reliable':reliable,
            'path':f"masks/mask_{index:04}.png"})
        cv2.imwrite(str(output/metrics[-1]['path']),persistent.astype(np.uint8)*255)
        previous_observed = observed
    # Bound memory: store one arrival map, not a dense frame stack.
    np.save(output/'birth_times.npy',birth,allow_pickle=False)
    final_area = int(persistent.sum())
    initially_present = int((final_color & base_color & base_valid).sum())
    warnings = []
    if baseline_unreliable:
        warnings.append('Baseline registration is unreliable; no claim of newly deposited paint can be established from it.')
    if not final_area:
        warnings.append('No persistent newly deposited foreground was established.')
    unreliable = sum(not r['reliable'] for r in records)
    if unreliable:
        warnings.append(f'{unreliable}/{len(records)} frames have unreliable registration; their observations were excluded.')
    if strategy == 'color':
        warnings.append('Colour-only segmentation includes pre-existing marks; stroke timing is not established for initial foreground.')
    temporal_evidence = final_area/max(1,int(candidate.sum()))
    if temporal_evidence < 0.1:
        warnings.append('Less than 10% of deposition candidates have persistent deposition evidence; footage may be static, edited, or unsuitable.')
    document = {'schema_version':1,'reference_size':frames['reference_size'],
        'source_sha256':frames['source_sha256'],'source_frames_manifest_sha256':sha256(path),
        'original_to_processed':frames['original_to_processed'],
        'reference_canvas':frames['reference_canvas'],
        'photo_original_to_reference':frames['photo_original_to_reference'],
        'config':{'strategy':strategy,'persistence':persistence,'ink':ink,'color':color,
                  'tolerance':tolerance,'roi':roi,'minimum_component':minimum_component,
                  'registration_tolerance':registration_tolerance},
        'final_mask':metrics[-1]['path'],'birth_times':'birth_times.npy',
        'candidate_pixels':int(candidate.sum()),'final_colour_pixels':int(final_color.sum()),'initially_present_color_pixels':initially_present,
        'persistent_deposition_fraction':temporal_evidence,'warnings':warnings,'frames':metrics}
    write_json(output/'segmentation.json',document)
    return document
