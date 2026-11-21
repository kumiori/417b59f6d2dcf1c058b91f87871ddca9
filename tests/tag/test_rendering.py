"""Numerical/structural validation; never print or inspect rendered art."""
import copy
from io import StringIO
import json
import subprocess
import sys
import pytest
from hube_tag.geometry import partial, validate
from hube_tag.raster import render, occupancy, cells
from hube_tag.animation import animate, splash, source_time


def document():
    return {'schema_version':1,'reference_size':[200,100],'strokes':[
        {'id':'one','kind':'polyline','points':[[0.1,0.5],[0.5,0.5],[0.9,0.5]],
         'point_times':[1,1.2,3],'t_start':1,'t_end':3,'width':0.01,'confidence':1}]}


def test_partial_uses_observed_velocity_and_interpolates_front():
    stroke = document()['strokes'][0]
    assert partial(stroke,0) == []
    assert partial(stroke,1.2) == stroke['points'][:2]
    assert partial(stroke,2.1)[-1] == pytest.approx([0.7,0.5])
    assert partial(stroke,3) == stroke['points']


def test_braille_bit_positions_and_rectangular_modes():
    for dy,bits in enumerate(((0,3),(1,4),(2,5),(6,7))):
        for dx,bit in enumerate(bits):
            grid = [bytearray(2) for _ in range(4)]
            grid[dy][dx] = 1
            assert cells(grid)[0] == chr(0x2800+(1<<bit))
    for mode in ('ascii','unicode','braille'):
        lines = render(document(),renderer=mode,columns=31,rows=12)
        assert len(lines) == 12 and all(len(line)==31 for line in lines)
        if mode == 'ascii':
            assert set(''.join(lines)) <= set(" /\\|-_.'()~+*")


def test_proportions_use_reference_dimensions_and_cell_aspect():
    doc = document()
    doc['strokes'][0]['points'] = [[0.1,0.1],[0.9,0.9]]
    doc['strokes'][0]['point_times'] = [1,3]
    grid,_ = occupancy(doc,columns=80,rows=40,cell_aspect_ratio=0.5)
    occupied = [(x,y) for y,row in enumerate(grid) for x,dot in enumerate(row) if dot]
    # x and y dot pitches both .25 with this cell aspect; physical slope is 1/2.
    xs,ys = zip(*occupied)
    assert (max(xs)-min(xs))/(max(ys)-min(ys)) == pytest.approx(2,rel=0.04)
    initial,_ = occupancy(doc,columns=80,rows=40,timestamp=0)
    assert not any(any(row) for row in initial)


def test_progressive_raster_is_monotone_and_timing_does_not_mutate():
    doc = document()
    saved = copy.deepcopy(doc)
    previous = set()
    for t in (0,1,1.1,1.2,2,3):
        grid,_ = occupancy(doc,columns=60,rows=20,timestamp=t)
        dots = {(x,y) for y,row in enumerate(grid) for x,v in enumerate(row) if v}
        assert previous <= dots
        previous = dots
    assert source_time(doc,0.25,'stylized') < source_time(doc,0.25,'original')
    assert doc == saved


def test_runtime_has_no_cv_dependencies():
    code = '''
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'cv2','numpy','scipy','skimage','PIL'}:
            raise AssertionError('CV dependency imported during playback')
sys.meta_path.insert(0,Block())
from hube_tag import render
import json
result=render(json.loads(sys.argv[1]), columns=40,rows=12)
assert len(result)==12
'''
    run = subprocess.run([sys.executable,'-S','-c',code,json.dumps(document())],capture_output=True,text=True)
    assert run.returncode == 0, run.stderr


class TTY(StringIO):
    def isatty(self):
        return True


class Clock:
    def __init__(self):
        self.now = 0
    def __call__(self):
        return self.now
    def sleep(self,delay):
        self.now += delay


def test_animation_restores_cursor_and_pipes_are_static():
    clock,output = Clock(),TTY()
    animate(document(),output=output,duration=0.2,fps=10,hold=0,clock=clock,sleep=clock.sleep)
    data = output.getvalue()
    assert '\x1b[?25l' in data and data.endswith('\x1b[?25h')
    assert '\x1b[2J' not in data
    def interrupt(delay):
        raise KeyboardInterrupt
    output = TTY()
    with pytest.raises(KeyboardInterrupt):
        animate(document(),output=output,clock=clock,sleep=interrupt)
    assert output.getvalue().endswith('\x1b[?25h')
    output = StringIO()
    def forbidden(delay):
        raise AssertionError('pipes must not wait')
    assert splash(document(),source=StringIO('1\n'),output=output,sleep=forbidden)
    assert '\x1b' not in output.getvalue()


def test_invalid_geometry_and_animation_inputs_fail_before_ansi():
    doc = document()
    doc['strokes'][0]['point_times'] = [1,3,2]
    with pytest.raises(ValueError):
        validate(doc)
    for options in ({'fps':float('nan')},{'duration':-1},{'hold':-1}):
        output = TTY()
        with pytest.raises(ValueError):
            animate(document(),output=output,**options)
        assert output.getvalue() == ''


def test_adaptive_bezier_preserves_loop_and_source_endpoints():
    from hube_tag.geometry import samples
    doc = document()
    stroke = doc['strokes'][0]
    stroke.pop('points')
    stroke.pop('point_times')
    stroke.update(kind='bezier',control_points=[[0.2,0.8],[0.1,0.1],[0.9,0.1],[0.8,0.8]])
    points,times = samples(stroke)
    assert len(points)>20 and points[0]==[0.2,0.8] and points[-1]==[0.8,0.8]
    assert min(p[1] for p in points)<0.3
    assert times[0]==1 and times[-1]==3
    assert len(render(doc,columns=50,rows=20))==20
