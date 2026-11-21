"""Deterministic video fixtures with known geometry, nonuniform velocity, and time."""
from pathlib import Path
import math
import cv2
import numpy as np
from scipy.spatial import cKDTree
from .geometry import partial, samples
from .io import write_json

CASES = ('line','circle','figure_eight','intersecting','self_intersecting','pen_up','camera_motion','occlusion')


def fixture(case):
    if case not in CASES:
        raise ValueError(f'unknown synthetic case {case}')
    def stroke(points,start,end):
        # Deliberately nonlinear velocity: timestamps encode slow -> fast motion.
        n = len(points)
        times = [start+(end-start)*(i/max(1,n-1))**0.7 for i in range(n)]
        return {'id':'','kind':'polyline','t_start':start,'t_end':end,'direction':'forward',
                'points':points,'point_times':times,'width':0.025,'confidence':1,'uncertainty':[]}
    u = np.linspace(0,1,181)
    line = [[0.16+0.68*t,0.25+0.5*t] for t in u]
    if case in ('line','camera_motion','occlusion'):
        strokes = [stroke(line,0.4,2.8)]
    elif case == 'circle':
        strokes = [stroke([[0.5+0.3*math.cos(2*math.pi*t),0.5+0.32*math.sin(2*math.pi*t)] for t in u],0.4,3.4)]
    elif case in ('figure_eight','self_intersecting'):
        # A figure-eight and a continuous crossed loop with an extended exit.
        points = [[0.5+0.33*math.sin(2*math.pi*t),0.5+0.33*math.sin(4*math.pi*t)] for t in u]
        if case == 'self_intersecting':
            corners = [(0.15,0.2),(0.85,0.8),(0.15,0.8),(0.85,0.2)]
            points = [[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]
                      for a,b in zip(corners,corners[1:]) for t in np.linspace(0,1,80,endpoint=False)] + [list(corners[-1])]
        strokes = [stroke(points,0.4,4.4)]
    elif case == 'intersecting':
        strokes = [stroke([[0.18+0.64*t,0.2+0.6*t] for t in u],0.4,1.9),
                   stroke([[0.2+0.6*t,0.8-0.6*t] for t in u],2.4,3.9)]
    else:
        strokes = [stroke([[0.12+0.3*t,0.3+0.2*t] for t in u],0.4,1.6),
                   stroke([[0.6+0.28*t,0.7-0.3*t] for t in u],2.5,3.8)]
    for i,s in enumerate(strokes,1):
        s['id'] = f'truth_{i:03}'
    return {'schema_version':1,'coordinate_system':'normalized','reference_size':[192,160],
            'strokes':strokes,'warnings':[],'synthetic_case':case}


def create_video(case, directory, *, fps=20):
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    document = fixture(case)
    write_json(directory/'truth.json',document)
    w,h = document['reference_size']
    rng = np.random.default_rng(1729)
    # Dense low-contrast texture gives camera registration stationary features.
    noise = rng.integers(20,110,(h,w),dtype=np.uint8)
    background = cv2.cvtColor(noise,cv2.COLOR_GRAY2BGR)
    background[:,:,1] = np.minimum(background[:,:,1]+15,150)
    # Pre-existing bright background mark must NOT be recovered as new paint.
    cv2.line(background,(5,10),(35,10),(245,245,245),3)
    path = directory/f'{case}.avi'
    writer = cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),fps,(w,h))
    if not writer.isOpened():
        raise ValueError('MJPG encoder unavailable')
    end = max(s['t_end'] for s in document['strokes'])+0.8
    try:
        for t in np.arange(0,end,1/fps):
            frame = background.copy()
            for stroke in document['strokes']:
                points = partial(stroke,float(t))
                if points:
                    pixels = np.rint(np.array(points)*[w,h]).astype(np.int32)
                    cv2.polylines(frame,[pixels],False,(245,245,245),5,cv2.LINE_8)
            if case == 'occlusion' and 1.1 <= t < 1.7:
                # Hand-shaped transient covers newly deposited paint and moves.
                center = (round(70+25*(t-1.1)),65)
                cv2.ellipse(frame,center,(20,15),15,0,360,(135,100,80),-1)
            if case == 'camera_motion':
                transform = np.float32([[1,0,3*math.sin(t*2)],[0,1,2*math.cos(t*1.3)]])
                frame = cv2.warpAffine(frame,transform,(w,h),borderMode=cv2.BORDER_REFLECT)
            writer.write(frame)
    finally:
        writer.release()
    return path,document


def score(truth, recovered):
    from .diagnostics import distance_metrics, vector_pixels
    size = np.array(truth['reference_size'])
    a,b = np.argwhere(vector_pixels(truth)),np.argwhere(vector_pixels(recovered))
    result = distance_metrics(a,b)
    gt_points,gt_times,gt_ids = [],[],[]
    for i,s in enumerate(truth['strokes']):
        points,times = samples(s)
        gt_points.extend(np.array(points)*size)
        gt_times.extend(times)
        gt_ids.extend([i]*len(points))
    tree = cKDTree(gt_points)
    errors, directions,order = [],[],[]
    for stroke in recovered['strokes']:
        points,times = samples(stroke)
        dist,indices = tree.query(np.array(points)*size)
        expected = np.array(gt_times)[indices]
        errors.extend(abs(np.array(times)-expected).tolist())
        observable = [(a,b) for a,b in zip(expected,expected[1:]) if abs(b-a)>0.02]
        if observable:
            directions.append(sum(b>a for a,b in observable)/len(observable))
        order.append(int(np.median(np.array(gt_ids)[indices])))
    result.update(stroke_count_error=len(recovered['strokes'])-len(truth['strokes']),
                  truth_strokes=len(truth['strokes']),recovered_strokes=len(recovered['strokes']),
                  time_mae_seconds=float(np.mean(errors)) if errors else None,
                  direction_accuracy=float(np.mean(directions)) if directions else None,
                  stroke_order_inversions=sum(a>b for a,b in zip(order,order[1:])),
                  ambiguity_count=sum(bool(s['uncertainty']) for s in recovered['strokes']))
    return result


def benchmark(output):
    from .pipeline import build
    from .io import read_json
    root = Path(output)
    results = {}
    for case in CASES:
        source,truth = create_video(case,root/case)
        build(source,root/case/'output',sample_hz=20,persistence=2)
        recovered = read_json(root/case/'output/trajectories.json')
        results[case] = score(truth,recovered)
    report = {'schema_version':1,'cases':results,
              'scope':'known synthetic geometry; not a guarantee of real-world or visual fidelity'}
    write_json(root/'benchmark.json',report)
    return report
