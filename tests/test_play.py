from game import load_fixture
from game.player import PlayerSession


def test_fixed_agency_and_recipient_owned_requests():
    game = load_fixture()
    andres = PlayerSession(game, 'person_002')
    editor = PlayerSession(game, 'person_003')
    result = andres.submit({'key': 'ask', 'kind': 'request', 'recipient_id': 'person_003', 'demand_id': 'rel_008'})
    assert result['ok'], result
    request = editor.inbox()[0]
    assert request['source_id'] == 'person_002'
    assert request['attributes']['demand_id'] == 'rel_008'
    before = game.get_world()
    assert not andres.submit({'key': 'forge', 'kind': 'respond', 'subject': request['id'], 'response': 'accept', 'actor': 'person_003'})['ok']
    assert not andres.submit({'key': 'wrong', 'kind': 'respond', 'subject': request['id'], 'response': 'accept'})['ok']
    assert game.get_world() == before
    assert editor.submit({'key': 'accept', 'kind': 'respond', 'subject': request['id'], 'response': 'accept'})['ok']
    assert editor.inbox() == []
    offers = [r for r in game.get_world()['relations'].values() if r['kind'] == 'offers']
    assert offers[0]['source_id'] == 'person_003'
    assert offers[0]['status'] == 'reported'
    assert game.project('now')['satisfied'] == 2
    assert game.replay().get_world() == game.get_world()


def test_decline_modify_and_hot_seat_are_explicit():
    import pytest
    game = load_fixture()
    session = PlayerSession(game, 'person_002')
    with pytest.raises(ValueError, match='hot_seat_required'):
        session.switch('person_003')
    hotseat = PlayerSession(game, 'person_002', hot_seat=True)
    hotseat.submit({'key': 'ask', 'kind': 'request', 'recipient_id': 'person_003', 'demand_id': 'rel_007'})
    hotseat.switch('person_003')
    rid = hotseat.inbox()[0]['id']
    assert hotseat.submit({'key': 'modify', 'kind': 'respond', 'subject': rid, 'response': 'modify', 'quantity': 1})['ok']
    offer = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'offers')
    assert offer['attributes']['quantity'] == 1
    assert offer['attributes']['request_id'] == rid
    assert game.project('now')['satisfied'] == 2
    hotseat.switch('person_002')
    hotseat.submit({'key': 'ask-again', 'kind': 'request', 'recipient_id': 'person_003', 'demand_id': 'rel_008'})
    hotseat.switch('person_003')
    rid = hotseat.inbox()[0]['id']
    assert hotseat.submit({'key': 'decline', 'kind': 'respond', 'subject': rid, 'response': 'decline'})['ok']
    assert game.get_world()['relations'][rid]['status'] == 'rejected'
    assert len([r for r in game.get_world()['relations'].values() if r['kind'] == 'offers']) == 1


def test_join_preserves_discovered_identity_and_provenance():
    game = load_fixture()
    result = game.submit({'key': 'observe', 'kind': 'observe', 'actor': 'person_002',
                          'source_id': 'person_001', 'node_kind': 'person', 'label': 'Photographer', 'relation_kind': 'knows'})
    assert result['ok']
    person = next(n for n in game.project('people') if n['label'] == 'Photographer')
    result = game.join('Photographer', key='join')
    assert result['ok']
    assert game.get_world()['nodes'][person['id']]['metadata']['playable']
    assert game.get_world()['nodes'][person['id']]['created_by'] == 'person_002'
    assert len(game.project('people')) == 5
    newcomer = PlayerSession(game, person['id'])
    assert newcomer.actor == person['id']
    assert game.replay().get_world() == game.get_world()


def test_correction_keeps_old_observation_in_history():
    game = load_fixture()
    result = game.submit({'key': 'observe', 'kind': 'observe', 'actor': 'person_002',
                          'target_id': 'person_003', 'relation_kind': 'knows'})
    assert result['ok']
    relation = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'knows')
    command = {'key': 'correct', 'kind': 'correct', 'actor': 'person_002', 'subject': relation['id'],
               'source_id': 'person_001', 'target_id': 'person_003', 'reason': 'Marco knows Editor, not me.'}
    assert game.submit(command)['ok']
    assert game.get_world()['relations'][relation['id']]['status'] == 'withdrawn'
    assert game.world_at(event=2)['relations'][relation['id']]['status'] == 'reported'
    corrected = next(r for r in game.get_world()['relations'].values() if r['metadata'].get('supersedes'))
    assert corrected['source_id'] == 'person_001'
    assert corrected['status'] == 'reported'
    assert not game.submit({**command, 'key': 'seed', 'subject': 'rel_001'})['ok']


def test_play_ui_binds_identity_without_running_the_scenario():
    from io import StringIO
    from game.play import run_play
    game = load_fixture()
    output = StringIO()
    run_play(game, StringIO('2\ns\n5\n4\nA reading\n0\n'), output)
    assert 'You are ANDRES.' in output.getvalue()
    assert 'development hot-seat' not in output.getvalue()
    assert all(a['submitted_by'] == 'person_002' for a in game.project('actions'))
    assert len(game.project('actions')) == 1
    assert not game.project('now')['feasible']
    assert 'THE GAME IS OVER.' not in output.getvalue()


def test_play_ui_join_and_hot_seat_inbox():
    from io import StringIO
    from game.play import run_play
    game = load_fixture()
    andres = PlayerSession(game, 'person_002')
    andres.submit({'key': 'ask', 'kind': 'request', 'recipient_id': 'person_003', 'demand_id': 'rel_008'})
    output = StringIO()
    run_play(game, StringIO('2\ns\n3\nr\n1\n1\n0\n'), output, hot_seat=True)
    assert 'You are EDITOR.' in output.getvalue()
    assert '1 requests are waiting for you.' in output.getvalue()
    assert any(r['kind'] == 'offers' and r['source_id'] == 'person_003' for r in game.get_world()['relations'].values())
    assert game.project('now')['satisfied'] == 2
    output = StringIO()
    run_play(game, StringIO('4\nAda\n0\n'), output)
    assert 'You are ADA.' in output.getvalue()
    assert any(n['label'] == 'Ada' and n['metadata']['playable'] for n in game.project('people'))


def full_play_input():
    lines = ['2']  # Andres; the next unresolved condition is always entry 1.
    def provide(quantity=1, venue=False):
        lines.extend(['1', '1', str(quantity), '1', '', ''])
        if venue:
            lines.extend(['1', 'Sala Comune'])
        else:
            lines.append('n')
        lines.extend(['y', 'y', '0'])  # connect, confirm, back to target
    def switch(who):
        lines.extend(['s', str(who)])
    def verify(note, final=False):
        lines.extend(['1', '8', '1', '2', note])
        if not final:
            lines.append('0')
    provide(venue=True)
    switch(3)
    verify('Venue confirmed.')
    provide()  # Editor confirms the date.
    switch(1)
    verify('Date agreed.')
    provide(quantity=2)  # Marco offers accommodation.
    switch(2)
    verify('Two beds confirmed.')
    provide()  # Andres offers documentation.
    switch(3)
    verify('Documentation agreed.', final=True)
    lines.append('y')
    return '\n'.join(lines) + '\n'


def test_complete_hot_seat_game_and_recap_come_from_player_input():
    from io import StringIO
    from game.play import run_play
    game = load_fixture()
    output = StringIO()
    run_play(game, StringIO(full_play_input()), output, hot_seat=True)
    assert game.project('now')['satisfied'] == 6, output.getvalue()[-2500:]
    assert 'HOW THIS BECAME FEASIBLE' in output.getvalue()
    assert 'Personal needs satisfied: 0' in output.getvalue()
    assert game.replay().get_world() == game.get_world()
    assert game.replay().project_journey() == game.project_journey()


def test_real_play_cli_and_saved_journey(tmp_path):
    import json
    import subprocess
    import sys
    prefix = [sys.executable, '-m', 'game', '--db', str(tmp_path / 'play.sqlite')]
    result = subprocess.run(prefix + ['play', 'hube-stop-01', '--hot-seat'],
                            input=full_play_input(), text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'HOW THIS BECAME FEASIBLE' in result.stdout
    journey = subprocess.run(prefix + ['journey', '--json'], text=True, capture_output=True, check=True)
    assert json.loads(journey.stdout)['reached'] is True
    history = subprocess.run(prefix + ['journey', '--at', '1'], text=True, capture_output=True, check=True)
    assert 'RECORDED SUPPORT SO FAR' in history.stdout
    assert 'No verified support yet.' in history.stdout


def test_italian_play_has_identical_world_and_localized_recap():
    from io import StringIO
    from game.play import run_play
    worlds = []
    for locale in ('en', 'it'):
        game, output = load_fixture(), StringIO()
        run_play(game, StringIO(full_play_input()), output, locale=locale, hot_seat=True)
        worlds.append(game.get_world())
        if locale == 'it':
            assert 'COME È DIVENTATO FATTIBILE' in output.getvalue()
            assert 'Sei ANDRES.' in output.getvalue()
    assert worlds[0] == worlds[1]


def test_invalid_request_operations_are_atomic_and_moves_are_read_only():
    game = load_fixture()
    session = PlayerSession(game, 'person_002')
    before = game.get_world(), game.project('log')
    assert session.possible_moves() == []
    moves = session.possible_moves(demand_id='rel_008', explore=True)
    assert any(m['kind'] == 'ask' for m in moves)
    assert before == (game.get_world(), game.project('log'))
    assert session.submit({'key': 'ask', 'kind': 'request', 'recipient_id': 'person_003', 'demand_id': 'rel_008'})['ok']
    request = PlayerSession(game, 'person_003').inbox()[0]
    before = game.get_world(), game.project('log')
    commands = [
        {'key': 'duplicate', 'kind': 'request', 'recipient_id': 'person_003', 'demand_id': 'rel_008'},
        {'key': 'bad-recipient', 'kind': 'request', 'recipient_id': 'place_001', 'demand_id': 'rel_008'},
        {'key': 'not-need', 'kind': 'request', 'recipient_id': 'person_003', 'demand_id': 'rel_001'},
    ]
    for command in commands:
        assert not session.submit(command)['ok']
    editor = PlayerSession(game, 'person_003')
    assert not editor.submit({'key': 'bad-quantity', 'kind': 'respond', 'subject': request['id'], 'response': 'modify', 'quantity': -1})['ok']
    assert before == (game.get_world(), game.project('log'))
