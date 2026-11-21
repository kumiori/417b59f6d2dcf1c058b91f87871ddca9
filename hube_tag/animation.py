"""TTY presentation only. No CV imports or game state."""
import math
import os
import shutil
import sys
import time
from .geometry import positive, validate
from .raster import render


def source_time(document, progress, timing='original'):
    start = min((s['t_start'] for s in document['strokes']), default=0)
    end = max((s['t_end'] for s in document['strokes']), default=start)
    if timing == 'stylized':
        progress = progress*progress*(3-2*progress)  # ease in/out; pauses survive
    elif timing != 'original':
        raise ValueError('timing must be original or stylized')
    return start + (end-start)*progress


def animate(document, *, output=None, renderer='braille', columns=None, rows=None,
            duration=None, fps=30, timing='original', hold=0.5,
            clock=time.monotonic, sleep=time.sleep, **options):
    """Animate into reserved lines. Pipes get one static frame without escapes.

    Resizes are re-measured per frame; the last frame remains. Cursor restoration
    is guaranteed by finally, including KeyboardInterrupt and output errors.
    """
    validate(document)
    positive(fps, 'fps')
    if fps > 120:
        raise ValueError('fps must be <= 120')
    if not math.isfinite(hold) or hold < 0:
        raise ValueError('hold must be finite and nonnegative')
    end = max((s['t_end'] for s in document['strokes']), default=0)
    start = min((s['t_start'] for s in document['strokes']), default=0)
    duration = max(end-start, 0.05) if duration is None else positive(duration, 'duration')
    source_time(document, 0, timing)  # validate before altering the terminal
    output = output if output is not None else sys.stdout
    tty = bool(getattr(output, 'isatty', lambda: False)())
    def dimensions():
        try:
            size = os.get_terminal_size(output.fileno())
        except (OSError, AttributeError, ValueError):
            size = shutil.get_terminal_size((100,36))
        return max(1, min(columns or size.columns, size.columns)), max(1, min(rows or 32, max(1,size.lines-3)))
    cols, height = dimensions()
    if not tty:
        output.write('\n'.join(render(document, renderer=renderer, columns=cols, rows=height, **options))+'\n')
        output.flush()
        return
    previous = []
    reserved = height
    try:
        output.write('\x1b[?25l' + '\n'*reserved + f'\x1b[{reserved}A\r')
        output.flush()
        began = clock()
        deadline = began
        while True:
            elapsed = clock()-began
            progress = min(1, max(0, elapsed/duration))
            cols, height = dimensions()
            # Never grow above the reserved region after a terminal resize.
            height = min(height, reserved)
            lines = render(document, renderer=renderer, columns=cols, rows=height,
                           timestamp=None if progress == 1 else source_time(document, progress, timing), **options)
            for i in range(max(len(lines),len(previous))):
                line = lines[i] if i < len(lines) else ''
                if i >= len(previous) or line != previous[i]:
                    output.write((f'\x1b[{i}B' if i else '')+'\r'+line+'\x1b[K'+(f'\x1b[{i}A' if i else ''))
            previous = lines
            output.flush()
            if progress == 1:
                break
            deadline += 1/fps
            sleep(max(0, deadline-clock()))
        sleep(hold)
    finally:
        output.write(f'\x1b[{reserved}B\r\x1b[?25h')
        output.flush()


def splash(document, *, source=None, output=None, prompt='> PRESS ENTER', **options):
    """Reusable splash API; returns False on EOF. Enter is consumed only on TTYs."""
    source = source if source is not None else sys.stdin
    output = output if output is not None else sys.stdout
    animate(document, output=output, **options)
    if getattr(source, 'isatty', lambda: False)() and getattr(output, 'isatty', lambda: False)():
        output.write(prompt+'\n')
        output.flush()
        return bool(source.readline())
    return True
