import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time

from game import Game


def test_profile_editor_shares_only_after_review_and_supports_keyboard_navigation(
    tmp_path,
):
    db = tmp_path / 'terminal.sqlite'
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 27, 104, 0, 0))
    before = termios.tcgetattr(slave)
    process = subprocess.Popen(
        [sys.executable, '-m', 'game', '--db', str(db), 'play'],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env={**os.environ, 'TERM': 'xterm-256color'},
    )
    captured = bytearray()

    def wait_for(fragment):
        deadline = time.monotonic() + 5
        while fragment not in captured and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                captured.extend(os.read(master, 65536))
        assert fragment in captured, captured.decode(errors='replace')
        captured.clear()

    def send(keys):
        os.write(master, keys)

    try:
        wait_for(b'My contributions')
        send(b'4')
        wait_for(b'Choose who you are:')
        send(b'1')
        wait_for(b'Edit shared profile')
        send(b'1')
        wait_for(b'Review & share')
        send(b' \r')
        wait_for(b'Keep draft')
        send('Photo & '.encode() + b'\x1bOP')
        wait_for(b'Your draft will be here when you return.')
        send('bvidéo\r'.encode())
        send(b'\x1bOB\t+')
        wait_for(b'Keep draft')
        send(b'A place to stay\r')
        send(b' s')
        wait_for(b'Enter Share profile')
        assert not Game.load(db).project('ecosystem')['declarations']
        send(b'\r')
        wait_for(b'World changed.')
        assert process.poll() is None
        saved = Game.load(db)
        assert {
            row['direction']: (row['description'], row['categories'])
            for row in saved.project('ecosystem')['declarations']
        } == {
            'offer': ('Photo & vidéo', ['creative']),
            'need': ('A place to stay', ['knowledge']),
        }
        send(b'1')
        wait_for(b'Review & share')
        send(b'-s')
        wait_for(b'Enter Share profile')
        send(b'\x1b')
        wait_for(b'Review & share')
        send(b'\x1b')
        wait_for(b'My contributions')
        assert Game.load(db).get_world() == saved.get_world()
        send(b'1')
        wait_for(b'Review & share')
        send(b'-s')
        wait_for(b'Enter Share profile')
        send(b'\r')
        wait_for(b'World changed.')
        final = Game.load(db)
        assert [
            row['description'] for row in final.project('ecosystem')['declarations']
        ] == ['A place to stay']
        assert 'Photo & vidéo' in [
            row['description']
            for row in final.project('ecosystem', at=2)['declarations']
        ]
        send(b'b')
        wait_for(b'Save and exit')
        send(b'0')
        deadline = time.monotonic() + 5
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                captured.extend(os.read(master, 65536))
        assert process.poll() == 0, captured.decode(errors='replace')
        after = termios.tcgetattr(slave)
        for state in (before, after):
            state[3] &= ~getattr(termios, 'PENDIN', 0)
        assert before == after
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


class InteractiveGame:
    """Read the real terminal output while driving a local save."""

    def __init__(self, database, *flags):
        self.master, self.slave = pty.openpty()
        self.resize(35, 124)
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'game', '--db', str(database), 'play', *flags],
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
            env={**os.environ, 'TERM': 'xterm-256color'},
        )
        self.captured = bytearray()

    def resize(self, rows, columns):
        fcntl.ioctl(
            self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0)
        )

    def collect(self):
        if select.select([self.master], [], [], 0.1)[0]:
            self.captured.extend(os.read(self.master, 65536))

    def expect(self, fragment):
        fragment = fragment.encode()
        deadline = time.monotonic() + 5
        while fragment not in self.captured and time.monotonic() < deadline:
            self.collect()
        assert fragment in self.captured, self.captured.decode(errors='replace')
        contents = bytes(self.captured)
        self.captured.clear()
        return contents

    def send(self, keys):
        os.write(self.master, keys.encode())

    def finish(self):
        self.send('0')
        deadline = time.monotonic() + 5
        while self.process.poll() is None and time.monotonic() < deadline:
            self.collect()
        assert self.process.poll() == 0, self.captured.decode(errors='replace')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        os.close(self.slave)
        os.close(self.master)


def test_graph_directory_and_resize_leave_the_clean_world_untouched(tmp_path):
    from signal import SIGWINCH

    database = tmp_path / 'graph.sqlite'
    with InteractiveGame(database) as terminal:
        terminal.expect('Explore the world')
        terminal.send('1')
        terminal.expect('All relationships')
        terminal.send('l')
        terminal.expect('Established')
        terminal.send('f')
        terminal.expect('People')
        terminal.resize(22, 72)
        terminal.process.send_signal(SIGWINCH)
        terminal.expect('Explore the world')
        terminal.send('t')
        terminal.expect('Presentation conditions')
        terminal.send('bb')
        terminal.expect('Save and exit')
        terminal.send('3')
        terminal.expect('Directory')
        terminal.send('/')
        terminal.expect('Search people')
        terminal.send('Editor\r')
        terminal.expect('Search · Editor')
        terminal.send('\r')
        terminal.expect('About me')
        terminal.send('bb')
        terminal.expect('Save and exit')
        terminal.finish()
    assert Game.load(database).project('now')['satisfied'] == 2
    assert len(Game.load(database).project('log')) == 1


def test_propose_and_redeem_contextual_invitation_through_terminal(tmp_path):
    import re

    database = tmp_path / 'invitation.sqlite'
    with InteractiveGame(database) as terminal:
        terminal.expect('Explore the world')
        terminal.send('2')
        terminal.expect('Choose who you are:')
        terminal.send('1')
        terminal.expect('Presentation proposals')
        terminal.send('2')
        terminal.expect('Propose a presentation')
        terminal.send('1')
        terminal.expect('oposed city')
        terminal.send('Paris\r')
        terminal.expect('date (YYYY-MM-DD)')
        terminal.send('2027-01-15\r')
        terminal.expect('venue (optional)')
        terminal.send('Le Grand Jeu\r')
        summary = terminal.expect('Share presentation proposal')
        assert b'Quantity?' not in summary
        terminal.send('2')
        terminal.expect('Paris')
        terminal.send('2')
        terminal.expect('Ask about this presentation')
        terminal.send('2')
        terminal.expect('Invite someone new')
        terminal.send('2')
        terminal.expect('What would you like them to help with?')
        terminal.send('Is Le Grand Jeu available on 15 January?\r')
        terminal.expect('Share request')
        terminal.send('2')
        receipt = terminal.expect('play --invite ')
        token = re.search(rb'play --invite ([A-Za-z0-9_-]+)', receipt)[1].decode()
        terminal.send('bbb')
        terminal.expect('Save and exit')
        terminal.finish()

    before = Game.load(database).get_world()
    candidate = next(
        n for n in before['nodes'].values() if n['metadata'].get('candidate_for')
    )
    assert candidate['metadata']['venue'] == 'Le Grand Jeu'
    assert candidate['metadata']['contributions'] == {}

    with InteractiveGame(database, '--invite', token) as terminal:
        terminal.expect('Is Le Grand Jeu available on 15 January?')
        terminal.send('1')
        terminal.expect('Choose who you are:')
        terminal.send('4')
        terminal.expect('Name?')
        terminal.send('Camille\r')
        terminal.expect('Save and exit')
        terminal.send('6')
        terminal.expect('Camille replied')
        terminal.send('b')
        terminal.expect('Save and exit')
        terminal.finish()

    saved = Game.load(database).get_world()
    invitation = next(
        n['metadata']['context_request']
        for n in saved['nodes'].values()
        if n['metadata'].get('context_request')
    )
    assert invitation['response'] == 'help'
    assert saved['nodes'][invitation['responder']]['label'] == 'Camille'
    assert saved['nodes'][candidate['id']]['metadata']['contributions'] == {}


def test_correct_a_place_from_my_contributions(tmp_path):
    from game import load_fixture

    database = tmp_path / 'correction.sqlite'
    game = load_fixture()
    result = game.submit(
        {
            'kind': 'observe',
            'key': 'notice',
            'actor': 'person_001',
            'node_kind': 'place',
            'label': 'Le Grand Jey',
        }
    )
    assert result['ok']
    place = next(
        row['entity_id'] for row in result['mutations'] if row['entity_type'] == 'node'
    )
    game.save(database)
    with InteractiveGame(database) as terminal:
        terminal.expect('My contributions')
        terminal.send('4')
        terminal.expect('Choose who you are:')
        terminal.send('1')
        terminal.expect('Le Grand Jey')
        terminal.send('2')
        terminal.expect('Correct the place name')
        terminal.send('1')
        terminal.expect('Press Enter to keep')
        terminal.send('Le Grand Jeu\r')
        terminal.expect('Correct place name to Le Grand Jeu?')
        terminal.send('2')
        terminal.expect('World changed.')
        terminal.send('b')
        terminal.expect('Save and exit')
        terminal.finish()
    saved = Game.load(database)
    assert saved.get_world()['nodes'][place]['label'] == 'Le Grand Jeu'
    assert saved.world_at(event=2)['nodes'][place]['label'] == 'Le Grand Jey'
