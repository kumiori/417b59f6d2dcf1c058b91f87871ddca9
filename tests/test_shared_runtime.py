"""The installed core must work without the old Commons compatibility package."""
from pathlib import Path
import subprocess
import sys


def test_game_uses_standalone_runtime_without_commons_wrapper():
    code = '''
import importlib.abc
import sys

class NoCommons(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'commons_engine' or fullname.startswith('commons_engine.'):
            raise AssertionError('HUBE still requires the unpublished commons-game wrapper')

sys.meta_path.insert(0, NoCommons())
from game import load_fixture
from game._shared import Mutation, WorldEngine, load_log, save_log
from game_gamer.history.events import Mutation as CoreMutation
from game_gamer.runtime.transactions import WorldEngine as CoreEngine
from game_gamer.persistence.log import load_log as core_load, save_log as core_save
assert Mutation is CoreMutation and WorldEngine is CoreEngine
assert load_log is core_load and save_log is core_save
world = load_fixture()
assert world.project('now')['satisfied'] == 2
assert world.replay().get_world() == world.get_world()
assert not any(name == 'commons_engine' or name.startswith('commons_engine.') for name in sys.modules)
'''
    run = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parents[1],
                         capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
