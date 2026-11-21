"""The disposable CLI plays against a snapshot and leaves the save intact."""

import subprocess
import sys

from game import Game, load_fixture


def test_sandbox_accepts_play_without_writing_existing_or_missing_saves(tmp_path):
    existing = tmp_path / 'shared.sqlite'
    load_fixture().save(existing)
    original = existing.read_bytes()
    for database in (existing, tmp_path / 'new.sqlite'):
        played = subprocess.run(
            [sys.executable, '-m', 'game', '--db', str(database), 'play', '--sandbox'],
            input='3\n4\nDisposable player\n0\n0\n',
            text=True,
            capture_output=True,
            check=True,
        )
        assert 'Disposable simulation' in played.stdout
        assert 'DISPOSABLE PLAYER' in played.stdout
    assert existing.read_bytes() == original
    assert len(Game.load(existing).project('log')) == 1
    assert not (tmp_path / 'new.sqlite').exists()
