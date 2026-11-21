"""Stage 1: timestamped video -> registered PNGs and frames.json.

FFprobe supplies per-frame presentation timestamps. No FPS-derived timestamps
are substituted if the container has missing/invalid presentation times.
"""
import json
import math
from pathlib import Path
import subprocess
import cv2
import numpy as np
from .io import sha256, write_json
from .registration import configure, register, photo_reference


def extract(source, output, *, sample_hz=12.5, max_dimension=640, change_threshold=0.12, reference_photo=None):
    if not math.isfinite(sample_hz) or sample_hz <= 0:
        raise ValueError('sample_hz must be finite and positive')
    if max_dimension < 32:
        raise ValueError('max_dimension must be >= 32')
    configure()
    output, source = Path(output), Path(source)
    directory = output/'frames'
    directory.mkdir(parents=True, exist_ok=True)
    try:
        probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-show_frames','-show_entries','frame=best_effort_timestamp_time:format=duration',
            '-of','json',str(source)], text=True, stderr=subprocess.PIPE))
    except subprocess.CalledProcessError as error:
        raise ValueError(f'cannot probe video: {error.stderr.strip()}') from error
    except FileNotFoundError as error:
        raise ValueError('ffprobe is required for original frame timestamps') from error
    timestamps = [float(f['best_effort_timestamp_time']) for f in probe['frames']]
    if not timestamps or any(not math.isfinite(t) for t in timestamps) or any(a >= b for a,b in zip(timestamps,timestamps[1:])):
        raise ValueError('video must provide finite, strictly increasing presentation timestamps')
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f'cannot open video: {source}')
    records = []
    last_selected = -float('inf')
    previous = None
    original_size = None
    try:
        for index, timestamp in enumerate(timestamps):
            ok, frame = capture.read()
            if not ok:
                raise ValueError('decoded frame count differs from presentation timestamps')
            h, w = frame.shape[:2]
            original_size = [w,h]
            factor = min(1, max_dimension/max(h,w))
            if factor < 1:
                frame = cv2.resize(frame, (round(w*factor),round(h*factor)), interpolation=cv2.INTER_AREA)
            processed_size = [frame.shape[1],frame.shape[0]]
            gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            diff = np.abs(gray.astype(float)-previous.astype(float)) if previous is not None else np.zeros_like(gray)
            score, changed = float(np.mean(diff)/255), float(np.mean(diff > 20))
            significant = changed > change_threshold
            if timestamp-last_selected >= 1/sample_hz-1e-7 or significant or index == len(timestamps)-1:
                frame_id = len(records)
                name = f'frame_{frame_id:04}.png'
                cv2.imwrite(str(directory/name), frame)
                records.append({'frame_id': frame_id, 'source_frame': index, 'timestamp': timestamp,
                    'path': f'frames/{name}', 'motion_score': score, 'foreground_change': changed,
                    'significant_change': significant, 'stationary': changed < 0.002,
                    'camera_transform': None})
                last_selected = timestamp
            previous = gray
    finally:
        capture.release()
    if not records:
        raise ValueError('no frames extracted')
    # Select within the final half-second: a stable, late frame, otherwise last.
    tail = [r for r in records if r['timestamp'] >= timestamps[-1]-0.5]
    stable = [r for r in tail if r['stationary']]
    chosen = (stable or tail)[-1]
    selection = {'method':'latest_stationary_tail_or_last'}
    if reference_photo:
        matched,selection = photo_reference(records,output,reference_photo)
        if matched is not None:
            chosen = matched
    reference = cv2.imread(str(output/chosen['path']))
    photo_transform = None
    if reference_photo:
        reference = cv2.imread(str(reference_photo))
        ph,pw = reference.shape[:2]
        factor = min(1,max_dimension/max(ph,pw))
        reference = cv2.resize(reference,(round(pw*factor),round(ph*factor)))
        photo_transform = [[reference.shape[1]/pw,0,0],[0,reference.shape[0]/ph,0],[0,0,1]]
    cv2.imwrite(str(output/'reference.png'),reference)
    h,w = reference.shape[:2]
    registered = output/'registered'
    registered.mkdir(exist_ok=True)
    target_gray = cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY)
    orb_features = cv2.ORB_create(nfeatures=2000,fastThreshold=12).detectAndCompute(target_gray,None)
    sift_features = cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.02).detectAndCompute(target_gray,None)
    for record in records:
        frame = cv2.imread(str(output/record['path']))
        warped, valid, metrics = register(frame, reference,orb_reference_features=orb_features,sift_reference_features=sift_features)
        record.update(metrics)
        name = f"frame_{record['frame_id']:04}.png"
        record['registered_path'] = f'registered/{name}'
        record['valid_path'] = f"registered/valid_{record['frame_id']:04}.png"
        cv2.imwrite(str(output/record['registered_path']), warped)
        cv2.imwrite(str(output/record['valid_path']), valid.astype(np.uint8)*255)
    document = {'schema_version':1, 'source_name':source.name,'source_sha256':sha256(source),
        'duration':float(probe['format'].get('duration',timestamps[-1]-timestamps[0])),
        'decoded_frames':len(timestamps),'selected_frames':len(records),'sample_hz':sample_hz,
        'sampling':'timestamp interval plus significant changes and final frame',
        'reference_frame_id':chosen['frame_id'], 'reference_selection':selection,
        'reference_path':'reference.png','reference_photo_sha256':sha256(reference_photo) if reference_photo else None,'reference_canvas':'photograph' if reference_photo else 'video_frame',
        'photo_original_to_reference':photo_transform, 'reference_size':[w,h],
        'original_size':original_size, 'processed_video_size':processed_size,
        'original_to_processed':[[processed_size[0]/original_size[0],0,0],[0,processed_size[1]/original_size[1],0],[0,0,1]],
        'frames':records}
    write_json(output/'frames.json',document)
    return document
