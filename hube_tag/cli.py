"""hube-tag: reproducible offline reconstruction and dependency-free playback."""
import argparse
import json
from pathlib import Path
import sys
from .io import read_json


def raster_options(parser):
    parser.add_argument('--renderer',choices=['ascii','unicode','braille'],default='braille')
    parser.add_argument('--columns',type=int,default=100)
    parser.add_argument('--rows',type=int,default=32)
    parser.add_argument('--cell-aspect-ratio',type=float,default=0.5,help='cell width / height')
    parser.add_argument('--stroke-thickness',type=float,default=1)
    parser.add_argument('--fit',choices=['tag','reference'],default='tag')


def segment_options(parser):
    parser.add_argument('--strategy',choices=['combined','color','temporal'],default='combined')
    parser.add_argument('--registration-tolerance',type=int,default=2,help='pixel radius for registered observation support')
    parser.add_argument('--persistence',type=int,default=3)
    parser.add_argument('--ink',choices=['light','dark'],default='light')
    parser.add_argument('--color',type=int,nargs=3,metavar=('R','G','B'))
    parser.add_argument('--tolerance',type=float,default=45)
    parser.add_argument('--roi',type=float,nargs=4,metavar=('X0','Y0','X1','Y1'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    for name in ('extract','build'):
        cmd = commands.add_parser(name)
        cmd.add_argument('input')
        cmd.add_argument('--output',required=True)
        cmd.add_argument('--sample-hz',type=float,default=12.5)
        cmd.add_argument('--max-dimension',type=int,default=640)
        cmd.add_argument('--reference-photo')
        if name == 'build':
            segment_options(cmd)
            cmd.add_argument('--pen-up-gap',type=float,default=0.6)
    cmd = commands.add_parser('segment')
    cmd.add_argument('manifest',help='frames.json, build directory, or frames/ directory')
    cmd.add_argument('--output')
    segment_options(cmd)
    cmd = commands.add_parser('reconstruct')
    cmd.add_argument('manifest',help='segmentation.json, build directory, or masks/ directory')
    cmd.add_argument('--output')
    cmd.add_argument('--pen-up-gap',type=float,default=0.6)
    cmd = commands.add_parser('validate')
    cmd.add_argument('directory')
    for name in ('render','animate','play'):
        cmd = commands.add_parser(name)
        cmd.add_argument('trajectories')
        raster_options(cmd)
        if name == 'render':
            cmd.add_argument('--output')
            cmd.add_argument('--timestamp',type=float)
        else:
            cmd.add_argument('--duration',type=float)
            cmd.add_argument('--fps',type=float,default=30)
            cmd.add_argument('--timing',choices=['original','stylized'],default='original')
    cmd = commands.add_parser('synthetic',help='generate and evaluate all eight known drawing videos')
    cmd.add_argument('--output',required=True)
    args = parser.parse_args(argv)
    values = vars(args).copy()
    name = values.pop('command')
    try:
        if name == 'extract':
            from .video import extract
            result = extract(values.pop('input'),**values)
            print(json.dumps({k:result[k] for k in ('duration','decoded_frames','selected_frames','reference_size')}))
        elif name == 'segment':
            from .segmentation import segment
            result = segment(**values)
            print(json.dumps({'candidate_pixels':result['candidate_pixels'],'warnings':result['warnings']}))
        elif name == 'reconstruct':
            from .trajectories import reconstruct
            result = reconstruct(**values)
            print(json.dumps({'stroke_count':len(result['strokes']),'warnings':result['warnings']}))
        elif name == 'build':
            from .pipeline import build
            result = build(values.pop('input'),**values)
            print(json.dumps({'geometry':result['geometry'],'warnings':result['warnings']}))
        elif name == 'validate':
            from .diagnostics import evaluate
            result = evaluate(**{'root':values['directory']})
            print(json.dumps({'geometry':result['geometry'],'warnings':result['warnings']}))
        elif name == 'synthetic':
            from .synthetic import benchmark
            print(json.dumps(benchmark(**values)))
        else:
            document = read_json(values.pop('trajectories'))
            if name == 'render':
                from .raster import render
                target = values.pop('output')
                text = '\n'.join(render(document,**values))+'\n'
                if target:
                    Path(target).write_text(text,encoding='utf-8')
                else:
                    sys.stdout.write(text)
            else:
                from .animation import animate,splash
                (splash if name == 'play' else animate)(document,**values)
        return 0
    except KeyboardInterrupt:
        return 130
    except ImportError as error:
        print(f'Offline processing requires the vision extra: pip install -e ".[vision]" ({error})',file=sys.stderr)
        return 1
    except (ValueError,OSError,KeyError) as error:
        print(f'hube-tag: {error}',file=sys.stderr)
        return 1
