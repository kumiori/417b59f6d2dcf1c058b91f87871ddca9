"""Integration stays outside world logic and does not consume piped game input."""
import json
import os
import subprocess
import sys


def test_game_can_invoke_standalone_splash_with_piped_play(tmp_path):
    document = {'schema_version':1,'reference_size':[100,100],'strokes':[
        {'id':'test','kind':'polyline','points':[[0.1,0.2],[0.8,0.7]],
         't_start':0,'t_end':1,'width':0.01}]}
    path = tmp_path/'curves.json'
    path.write_text(json.dumps(document))
    db = tmp_path/'game.sqlite'
    run = subprocess.run([sys.executable,'-m','game','--db',str(db),'play','hube-stop-01',
                          '--splash',str(path),'--splash-duration','0.05'],
                          input='1\n0\n',text=True,capture_output=True,timeout=10)
    assert run.returncode == 0, run.stderr
    assert db.exists()
    assert '\x1b' not in run.stdout and '> PRESS ENTER' not in run.stdout
    assert 'You are MARCO.' in run.stdout
