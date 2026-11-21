from io import StringIO
from game import load_fixture
from game.terminal import run_session


def test_terminal_observation_is_engine_command():
    game = load_fixture()
    output = StringIO()
    run_session(game, StringIO('1\n1\nGiulia\n0\n'), output)
    assert any(n['label'] == 'Giulia' for n in game.project('people'))
    assert 'World changed.' in output.getvalue()
    assert '2 / 6' in output.getvalue()
    assert game.replay().get_world() == game.get_world()


def test_terminal_full_game_and_same_game_in_italian():
    import json
    from pathlib import Path
    scenario = json.loads((Path(__file__).parent / 'scenarios/hube_stop_01.yaml').read_text())
    reference = load_fixture()
    for command in scenario['commands']:
        result = reference.submit(command)
        assert result['ok'], result
    expected = json.loads((Path(__file__).parent / 'scenarios/hube_stop_01.expected.json').read_text())
    assert reference.get_world() == expected
    assert reference.project('now')['feasible'] is True
    assert reference.project('now')['satisfied'] == 6
    assert len(reference.project('log')) == 20
    for locale, ending in [('en', 'THE GAME IS OVER.'), ('it', 'IL GIOCO È FINITO.')]:
        game = load_fixture()
        output = StringIO()
        run_session(game, StringIO(scenario['terminal_input']), output, locale=locale)
        assert ending in output.getvalue(), output.getvalue()[-2500:]
        assert game.get_world() == reference.get_world()
        assert game.project('log') == reference.project('log')
        assert game.replay().get_world() == reference.get_world()


def test_real_cli_persists_and_inspects_full_game(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    scenario = json.loads((Path(__file__).parent / 'scenarios/hube_stop_01.yaml').read_text())
    db = tmp_path / 'game.sqlite'
    prefix = [sys.executable, '-m', 'game', '--db', str(db)]
    run = subprocess.run(prefix + ['start', 'hube-stop-01'], input=scenario['terminal_input'], text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert 'THE GAME IS OVER.' in run.stdout
    replay = subprocess.run(prefix + ['replay'], text=True, capture_output=True, check=True)
    world = subprocess.run(prefix + ['world'], text=True, capture_output=True, check=True)
    assert json.loads(replay.stdout) == json.loads(world.stdout)
    historical = subprocess.run(prefix + ['network', '--at', 'T4'], text=True, capture_output=True, check=True)
    network = json.loads(historical.stdout)
    assert any(n['label'] == 'Sala Comune' for n in network['nodes'])
    assert not any(r['kind'] == 'satisfies' for r in network['relations'])
    for projection in ['people', 'resources', 'requirements', 'log', 'timeline']:
        inspected = subprocess.run(prefix + [projection], text=True, capture_output=True)
        assert inspected.returncode == 0, inspected.stderr
    restarted = subprocess.run(prefix + ['start', 'hube-stop-01'], text=True, capture_output=True)
    assert restarted.returncode == 1
    assert json.loads(subprocess.run(prefix + ['world'], text=True, capture_output=True, check=True).stdout) == json.loads(world.stdout)


def test_quit_and_resume_preserve_the_partial_world(tmp_path):
    from game import Game
    game = load_fixture()
    db = tmp_path / 'resume.sqlite'
    run_session(game, StringIO('1\n1\nGiulia\n0\n'), StringIO(), on_change=lambda g: g.save(db))
    loaded = Game.load(db)
    run_session(loaded, StringIO('4\nOpen reading\n0\n'), StringIO(), on_change=lambda g: g.save(db))
    assert any(n['label'] == 'Giulia' for n in loaded.project('people'))
    assert any(n['label'] == 'Open reading' for n in loaded.project('network')['nodes'])
    assert not loaded.project('now')['feasible']
