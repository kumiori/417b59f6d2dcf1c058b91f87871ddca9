import json
from io import StringIO
from pathlib import Path

from game.replay import simulate, ReplayDriver


def test_semantic_replay_preserves_canonical_world_and_causal_order():
    game, events = simulate()
    expected = json.loads(Path('tests/scenarios/hube_stop_01.expected.json').read_text())
    assert game.get_world() == expected
    kinds = [e.kind for e in events]
    assert kinds[0] == 'initial'
    assert kinds[-1] == 'ending'
    assert kinds.count('threshold') == 4
    assert 'possibility' in kinds
    giulia = [e for e in events if e.sequence == 2]
    assert [e.kind for e in giulia] == ['player_action', 'mutation', 'relation_created']
    output = StringIO()
    ReplayDriver(output=output, mode='instant').play(events)
    assert 'Giulia entered the world.' in output.getvalue()
    assert 'THE GAME IS OVER.' in output.getvalue()
    assert 'Content-Type:' not in output.getvalue()
    assert game.replay().get_world() == expected


class Clock:
    def __init__(self, keys=()):
        self.now = 0.0
        self.keys = iter(keys)

    def __call__(self):
        return self.now

    def read(self, timeout):
        self.now += timeout
        return next(self.keys, None)


def test_pacing_scales_without_changing_transcript():
    from game.replay import BASE_DELAYS
    _, events = simulate()
    expected = sum(BASE_DELAYS[e.kind] for e in events)
    transcripts = []
    for speed in (.5, 1, 2):
        clock, output = Clock(), StringIO()
        driver = ReplayDriver(output=output, mode='paced', speed=speed, clock=clock, read_key=clock.read)
        assert driver.play(events)
        assert abs(clock.now - expected / speed) < 1e-6
        transcripts.append(output.getvalue())
    assert transcripts[0] == transcripts[1] == transcripts[2]


def test_pause_step_speed_and_quit():
    _, events = simulate()
    clock = Clock([' ', '+', '\x1b[C', '-', '\x1b[D', '\n', 'q'])
    output = StringIO()
    driver = ReplayDriver(output=output, mode='paced', clock=clock, read_key=clock.read)
    assert driver.play(events) is False
    assert driver.paused  # Enter advanced exactly one event without unpausing.
    assert driver.speed == 1
    assert 'I know Giulia.' in output.getvalue()
    assert 'Giulia entered the world.' not in output.getvalue()
    assert 'THE GAME IS OVER.' not in output.getvalue()


def test_step_uses_input_instead_of_pacing_and_can_resume():
    _, events = simulate()
    clock = Clock(['\n', ' ', 'q'])
    output = StringIO()
    driver = ReplayDriver(output=output, mode='step', read_key=clock.read, clock=clock)
    assert driver.play(events) is False
    assert not driver.paused
    assert 'I know Giulia.' in output.getvalue()


def test_instant_never_waits_and_invalid_speed_is_rejected():
    import pytest
    _, events = simulate()
    def forbidden(*args):
        raise AssertionError('instant mode must never wait')
    assert ReplayDriver(output=StringIO(), read_key=forbidden, mode='instant').play(events)
    for speed in (0, -1, float('nan'), float('inf')):
        with pytest.raises(ValueError):
            ReplayDriver(speed=speed)


def test_cli_modes_and_packaged_scenario():
    import subprocess
    import sys
    source = json.loads(Path('tests/scenarios/hube_stop_01.yaml').read_text())
    assert json.loads(Path('game/scenarios/hube_stop_01.json').read_text()) == source
    for prefix in ([sys.executable, 'tools/play_scenario.py'], [sys.executable, '-m', 'game', 'simulate', 'hube-stop-01']):
        result = subprocess.run(prefix + ['--instant'], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert 'THE GAME IS OVER.' in result.stdout
        assert '\x1b' not in result.stdout
        assert 'What did you observe?' not in result.stdout
        result = subprocess.run(prefix + ['--step'], input='', capture_output=True, text=True, timeout=10)
        assert result.returncode == 1
        assert 'requires a terminal' in result.stderr
        for args in (['--speed', '0'], ['--speed', 'nan'], ['--step', '--paced']):
            result = subprocess.run(prefix + args, capture_output=True, text=True, timeout=10)
            assert result.returncode == 2


def test_real_tty_controls_and_terminal_restoration():
    import os
    import pty
    import select
    import subprocess
    import sys
    import termios
    import time
    master, slave = pty.openpty()
    before = termios.tcgetattr(slave)
    process = subprocess.Popen([sys.executable, '-m', 'game', 'simulate', 'hube-stop-01', '--step'],
                               stdin=slave, stdout=slave, stderr=slave)
    captured = b''
    def wait_for(fragment):
        nonlocal captured
        deadline = time.monotonic() + 5
        while fragment not in captured and time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]:
                captured += os.read(master, 65536)
        assert fragment in captured, captured.decode(errors='replace')
    try:
        wait_for(b'paused')
        os.write(master, b'+')
        wait_for('×2.0'.encode())
        os.write(master, b'\x1b[D')
        # Enter advances while remaining paused; the next statement is visible.
        os.write(master, b'\r')
        wait_for(b'I know Giulia.')
        os.write(master, b'q')
        deadline = time.monotonic() + 5
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]:
                captured += os.read(master, 65536)
        assert process.wait(timeout=1) == 0
        restored = termios.tcgetattr(slave)
        # Darwin marks pending input for reprocessing on return to canonical mode.
        restored[3] &= ~getattr(termios, 'PENDIN', 0)
        before[3] &= ~getattr(termios, 'PENDIN', 0)
        assert restored == before
        assert b'THE GAME IS OVER.' not in captured
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


def test_italian_replay_changes_only_presentation():
    en_game, en_events = simulate(locale='en')
    it_game, it_events = simulate(locale='it')
    assert en_game.get_world() == it_game.get_world()
    assert en_game.project('log') == it_game.project('log')
    assert [e.kind for e in en_events] == [e.kind for e in it_events]
    assert 'IL GIOCO È FINITO.' in it_events[-1].text


def test_human_beats_breathe_and_recap_is_opt_in_for_pipes():
    import subprocess
    import sys
    from game.replay import BASE_DELAYS
    assert BASE_DELAYS['player_action'] == 2.5
    assert BASE_DELAYS['mutation'] == BASE_DELAYS['relation_created'] == .5
    prefix = [sys.executable, 'tools/play_scenario.py', '--instant']
    result = subprocess.run(prefix + ['--recap'], capture_output=True, text=True, check=True)
    assert 'HOW THIS BECAME FEASIBLE' in result.stdout
    result = subprocess.run(prefix + ['--no-recap'], capture_output=True, text=True, check=True)
    assert 'HOW THIS BECAME FEASIBLE' not in result.stdout
    assert 'See how we got here?' not in result.stdout
