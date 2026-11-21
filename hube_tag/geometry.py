"""Pure-Python curves, timing, and dimension-preserving transforms.

Coordinates are normalized to the entire reference image, NOT a square canvas.
point_times are seconds in source-video time and may be nonuniform.
"""
import math


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')
    return value


def validate(document):
    if document.get('schema_version') != 1:
        raise ValueError('unsupported trajectory schema_version')
    width, height = document['reference_size']
    positive(width, 'reference width')
    positive(height, 'reference height')
    ids = set()
    for stroke in document['strokes']:
        if stroke['id'] in ids:
            raise ValueError('duplicate stroke id')
        ids.add(stroke['id'])
        start, end = stroke['t_start'], stroke['t_end']
        if not all(math.isfinite(v) for v in (start, end)) or start < 0 or end < start:
            raise ValueError('invalid stroke interval')
        if stroke.get('kind', 'polyline') not in ('polyline', 'bezier'):
            raise ValueError('kind must be polyline or bezier')
        points = stroke.get('points', stroke.get('control_points', []))
        if not points or any(len(p) != 2 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in points):
            raise ValueError('points must be finite normalized coordinates')
        if stroke.get('kind', 'polyline') == 'bezier' and len(points) != 4:
            raise ValueError('cubic Bézier requires four control points')
        positive(stroke['width'], 'stroke width')
        times = stroke.get('point_times')
        if times is not None and (len(times) != len(points) or
                any(not math.isfinite(t) or t < start or t > end for t in times) or
                any(a > b for a, b in zip(times, times[1:]))):
            raise ValueError('point_times must be monotone and within the stroke interval')
    return document


def length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def bezier(points, tolerance=0.001):
    """Adaptive de Casteljau subdivision, preserving sharp turns and loops."""
    a, b, c, d = points
    chord = math.dist(a, d)
    if length(points) - chord <= tolerance and chord <= 0.025:
        return [list(a), list(d)]
    ab, bc, cd = [[(p[i] + q[i]) / 2 for i in (0, 1)] for p, q in ((a,b), (b,c), (c,d))]
    abc, bcd = [[(p[i] + q[i]) / 2 for i in (0, 1)] for p, q in ((ab,bc), (bc,cd))]
    mid = [(abc[i] + bcd[i]) / 2 for i in (0, 1)]
    return bezier([a, ab, abc, mid], tolerance)[:-1] + bezier([mid, bcd, cd, d], tolerance)


def samples(stroke):
    points = stroke.get('points', stroke.get('control_points'))
    if stroke.get('kind') == 'bezier':
        points = bezier(points)
    times = stroke.get('point_times')
    if times is None:
        distances = [0.0]
        for a, b in zip(points, points[1:]):
            distances.append(distances[-1] + math.dist(a, b))
        total = distances[-1]
        times = [stroke['t_start'] + (stroke['t_end'] - stroke['t_start']) * d / total
                 if total else stroke['t_start'] for d in distances]
    return points, times


def partial(stroke, timestamp=None):
    points, times = samples(stroke)
    if timestamp is None or timestamp >= stroke['t_end']:
        return points
    if timestamp < stroke['t_start']:
        return []
    result = []
    for i, (point, time) in enumerate(zip(points, times)):
        if time <= timestamp:
            result.append(point)
        else:
            if i and times[i] > times[i-1] and timestamp > times[i-1]:
                fraction = (timestamp-times[i-1])/(times[i]-times[i-1])
                result.append([points[i-1][k] + fraction*(point[k]-points[i-1][k]) for k in (0,1)])
            break
    return result


def bounds(document):
    points = [p for s in document['strokes'] for p in samples(s)[0]]
    if not points:
        return (0, 0, 1, 1)
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)
