"""Dependency-free renderer: trajectories -> common 2x4 occupancy -> cells."""
import math
from .geometry import bounds, partial, positive, validate

BRAILLE_BITS = ((0, 3), (1, 4), (2, 5), (6, 7))
MODES = ('ascii', 'unicode', 'braille')


def occupancy(document, *, columns=100, rows=32, cell_aspect_ratio=0.5,
              stroke_thickness=1.0, timestamp=None, fit='tag'):
    validate(document)
    if timestamp is not None and not math.isfinite(timestamp):
        raise ValueError('timestamp must be finite')
    if not isinstance(columns, int) or not isinstance(rows, int) or min(columns, rows) < 1:
        raise ValueError('columns and rows must be positive integers')
    positive(cell_aspect_ratio, 'cell_aspect_ratio (width / height)')
    positive(stroke_thickness, 'stroke_thickness')
    if fit not in ('tag', 'reference'):
        raise ValueError('fit must be tag or reference')
    # Physical display units: cell height=1, width=cell_aspect_ratio.
    rw, rh = document['reference_size']
    x0, y0, x1, y1 = bounds(document) if fit == 'tag' else (0, 0, 1, 1)
    max_width = max((s['width'] for s in document['strokes']), default=0) * rw * stroke_thickness
    width, height = max((x1-x0)*rw, 1) + max_width, max((y1-y0)*rh, 1) + max_width
    scale = min(max(columns-2, 1)*cell_aspect_ratio/width, max(rows-2, 1)/height)
    ox = (columns*cell_aspect_ratio-(x1-x0)*rw*scale)/2
    oy = (rows-(y1-y0)*rh*scale)/2
    grid = [bytearray(columns*2) for _ in range(rows*4)]
    # Subpixels have different physical pitches; disk stamping respects both.
    pitch_x, pitch_y = cell_aspect_ratio/2, 0.25
    def transform(point):
        return ((ox+(point[0]-x0)*rw*scale)/pitch_x - 0.5,
                (oy+(point[1]-y0)*rh*scale)/pitch_y - 0.5)
    for stroke in document['strokes']:
        points = [transform(p) for p in partial(stroke, timestamp)]
        radius = max(stroke['width']*rw*scale*stroke_thickness/2, min(pitch_x, pitch_y)*0.52)
        rx, ry = radius/pitch_x, radius/pitch_y
        def stamp(x, y):
            for iy in range(max(0, math.ceil(y-ry)), min(rows*4, math.floor(y+ry)+1)):
                for ix in range(max(0, math.ceil(x-rx)), min(columns*2, math.floor(x+rx)+1)):
                    if ((ix-x)/rx)**2 + ((iy-y)/ry)**2 <= 1:
                        grid[iy][ix] = 1
            # Subpixel-width lines still deposit their nearest sample.
            ix, iy = round(x), round(y)
            if 0 <= ix < columns*2 and 0 <= iy < rows*4:
                grid[iy][ix] = 1
        if len(points) == 1:
            stamp(*points[0])
        for a, b in zip(points, points[1:]):
            count = max(1, math.ceil(math.dist(a,b)*2))
            for j in range(count+1):
                u = j/count
                stamp(a[0]+u*(b[0]-a[0]), a[1]+u*(b[1]-a[1]))
    return grid, {'scale': scale, 'offset': [ox,oy], 'bounds': [x0,y0,x1,y1],
                  'reference_size': [rw,rh], 'pitch': [pitch_x,pitch_y]}


def cells(grid, mode='braille'):
    if mode not in MODES:
        raise ValueError(f'unknown renderer: {mode}')
    rows, columns = len(grid)//4, len(grid[0])//2
    result = []
    for y in range(rows):
        line = []
        for x in range(columns):
            dots = [(dx,dy) for dy in range(4) for dx in range(2) if grid[y*4+dy][x*2+dx]]
            if not dots:
                char = ' '
            elif mode == 'braille':
                char = chr(0x2800 + sum(1 << BRAILLE_BITS[dy][dx] for dx,dy in dots))
            else:
                # Principal local orientation with neighboring occupied dots gives
                # deterministic line art; both alternatives use the SAME raster.
                cloud = [(xx,yy) for yy in range(max(0,y*4-2),min(rows*4,y*4+6))
                         for xx in range(max(0,x*2-1),min(columns*2,x*2+3)) if grid[yy][xx]]
                mx, my = sum(p[0] for p in cloud)/len(cloud), sum(p[1] for p in cloud)/len(cloud)
                vx = sum((p[0]-mx)**2 for p in cloud)
                vy = sum((p[1]-my)**2 for p in cloud)
                cross = sum((p[0]-mx)*(p[1]-my) for p in cloud)
                # Normalize pixel coordinates to conventional terminal proportions.
                angle = 0.5*math.atan2(2*cross, vx-vy)
                if len(dots) == 1:
                    char = '.'
                elif abs(angle) < math.pi/8:
                    char = '-' if mode == 'ascii' else '─'
                elif abs(angle) > 3*math.pi/8:
                    char = '|' if mode == 'ascii' else '│'
                elif angle > 0:
                    char = '\\' if mode == 'ascii' else '╲'
                else:
                    char = '/' if mode == 'ascii' else '╱'
            line.append(char)
        result.append(''.join(line))
    return result


def render(document, *, renderer='braille', **options):
    """Return a rectangular list[str]. width/height are terminal cells."""
    grid, _ = occupancy(document, **options)
    return cells(grid, renderer)
