from io import StringIO
from game import load_fixture
from game.player import PlayerSession


def test_resource_resolution_requires_explicit_distinct_identity():
    game = load_fixture()
    command = {'key': 'duplicate', 'kind': 'observe', 'actor': 'person_002',
               'node_kind': 'resource', 'label': '  accommodation  ', 'relation_kind': 'suggests'}
    before = game.get_world()
    assert not game.submit(command)['ok']
    assert game.get_world() == before
    candidates = game.resolve_resources(' ACCOMMODATION ')
    assert candidates[0]['id'] == 'resource_005'
    assert candidates[0]['required_by'] == ['event_001']
    assert game.submit({**command, 'allow_duplicate_resource': True})['ok']
    assert len(game.resolve_resources('accommodation')) == 2
    assert game.replay().get_world() == game.get_world()


def test_relation_signatures_prevent_category_errors_atomically():
    game = load_fixture()
    before = game.get_world()
    assert not game.submit({'key': 'bad', 'kind': 'observe', 'actor': 'person_001',
                            'target_id': 'resource_006', 'relation_kind': 'knows'})['ok']
    assert game.get_world() == before
    assert 'knows' not in game.valid_observation_relations('person_001', 'resource_006')
    assert 'located_in' in game.valid_observation_relations('event_001', 'place_001')
    assert game.submit({'key': 'place', 'kind': 'observe', 'actor': 'person_002',
                        'source_id': 'event_001', 'target_id': 'place_001', 'relation_kind': 'located_in'})['ok']


def test_player_moves_are_grounded_unless_one_need_is_explored():
    game = load_fixture()
    player = PlayerSession(game, 'person_002')
    before = game.get_world(), game.project('log')
    assert player.possible_moves() == []
    explore = player.possible_moves(demand_id='rel_007', explore=True)
    assert len(explore) == 3
    assert all(m['tier'] == 'exploratory' and m['target_ids'] == ['rel_007'] for m in explore)
    assert before == (game.get_world(), game.project('log'))


def test_dialogue_recovers_locally_and_back_discards_dependent_answers():
    from game.dialogue import Dialogue
    output = StringIO()
    d = Dialogue(StringIO('not a choice\n?\n1\nnot a number\nb\n2\n4\n'), output)
    result = d.run(lambda form: (form.choose('Choose', ['first', 'second']), form.quantity()))
    assert result == ('second', 4)
    assert output.getvalue().count('Choose\n') == 4
    assert 'I need one of the listed choices.' in output.getvalue()
    assert 'Quantity must be a positive integer.' in output.getvalue()
    assert Dialogue(StringIO('first\n0\n'), StringIO()).run(lambda form: (form.text('Name'), form.quantity())) is None


def funding_and_beds_input():
    return '\n'.join([
        '2',                    # Andres
        '5', '3', '5', 'Funding', '3000', 'eur', '1', '', '',
        '3', '1', '1', '1', '', '', 'n', 'y', 'y', '0',
        's', '3',               # Editor
        '3', '8', '1', '2', 'One bed verified.',
        '1', '1', '1', '', '', 'n', 'y', 'y', '0',
        's', '2',               # Andres
        '3', '8', '1', '2', 'Second bed verified.', '0', '0',
    ]) + '\n'


def test_goal_traversal_funding_then_two_beds():
    from game.play import run_play
    game, output = load_fixture(), StringIO()
    run_play(game, StringIO(funding_and_beds_input()), output, hot_seat=True)
    text = output.getvalue()
    assert 'Accommodation — unsatisfied' in text
    assert 'Offered: 1/2 · committed: 0/2 · verified: 0/2' in text
    assert '1 / 2 bed secured.' in text
    assert '2 / 2 bed secured.' in text
    assert 'ACCOMMODATION ✓' in text
    assert game.get_world()['requirements']['requirement_005']['status'] == 'satisfied', text[-3500:]
    assert len(game.get_world()['requirements']) == 6
    assert game.project('now')['satisfied'] == 3
    funding = next(n for n in game.project('resources') if n['label'] == 'Funding')
    need = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'needs')
    assert need['target_id'] == funding['id']
    assert need['attributes']['quantity'] == 3000
    assert need['attributes']['unit'] == 'eur'
    assert 'OTHER NEEDS DISCOVERED DURING PLAY (not ending conditions)' in text
    assert len(game.resolve_resources('accommodation')) == 1
    assert game.replay().get_world() == game.get_world()
    assert 'Which specific place or object?' not in text


def test_cancelled_offer_creates_no_nodes_and_invalid_input_stays_in_form():
    from game.play import run_play
    game, output = load_fixture(), StringIO()
    # New city is only a field value until all offer fields are validated.
    script = '2\n3\n1\none\n1\n2\nNew city\nb\nb\n1\nbad-date\n?\n0\n0\n0\n'
    run_play(game, StringIO(script), output)
    assert len(game.project('log')) == 1
    assert not any(n['label'] == 'New city' for n in game.project('places'))
    assert 'Quantity must be a positive integer.' in output.getvalue()
    assert 'Enter a valid date, not earlier than the start date (YYYY-MM-DD).' in output.getvalue()


def test_observation_resolves_existing_category_without_offering_it():
    from game.play import run_play
    game, output = load_fixture(), StringIO()
    # Add -> observation -> need/resource -> new -> normalized existing candidate.
    run_play(game, StringIO('2\n5\n1\n2\n5\n accommodation \n1\n0\n'), output)
    assert 'This may already exist:' in output.getvalue()
    assert 'required by HUBE / STOP 01' in output.getvalue()
    assert len(game.resolve_resources('accommodation')) == 1
    relation = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'suggests')
    assert relation['target_id'] == 'resource_005'
    assert not any(r['kind'] == 'offers' for r in game.get_world()['relations'].values())


def test_existing_duplicate_nodes_do_not_redirect_goal_offers_or_break_replay():
    from game.play import run_play
    game = load_fixture()
    for i in range(2):
        assert game.submit({'key': f'legacy-{i}', 'kind': 'observe', 'actor': 'person_004',
                            'node_kind': 'resource', 'label': 'accommodation', 'relation_kind': 'suggests',
                            'allow_duplicate_resource': True})['ok']
    before = game.project('log')
    game = game.replay()
    output = StringIO()
    run_play(game, StringIO('2\n7\n3\n1\n1\n1\n\n\nn\ny\ny\n0\n0\n'), output)
    assert 'separate resource, not this event’s requirement' in output.getvalue()
    offers = [r for r in game.get_world()['relations'].values() if r['kind'] == 'offers']
    assert len(offers) == 1
    assert offers[0]['target_id'] == 'resource_005'
    assert len(game.resolve_resources('accommodation')) == 3  # no silent destructive merge
    assert game.project('log')[:len(before)] == before


def test_relationship_dialogue_includes_places_and_filters_signatures():
    from game.play import run_play
    game, output = load_fixture(), StringIO()
    run_play(game, StringIO('2\n5\n1\n6\nshow other entities\n5\n11\n1\n0\n'), output)
    assert output.getvalue().count('Choose the source.') == 2
    assert '\n  1  knows\n' not in output.getvalue()
    observation = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'suggests')
    assert observation['source_id'] == 'place_001'
    assert observation['target_id'] == 'resource_006'


def test_new_location_and_concrete_asset_are_created_atomically():
    game = load_fixture()
    command = {'key': 'new', 'kind': 'offer', 'actor': 'person_002', 'resource_id': 'resource_003',
               'quantity': 1, 'unit': 'venue', 'location_label': 'Another city', 'asset_label': 'A hall',
               'asset_kind': 'place', 'available_from': '2026-11-14', 'available_until': '2026-11-13'}
    before = game.get_world()
    assert not game.submit(command)['ok']
    assert game.get_world() == before
    assert game.submit({**command, 'available_until': '2026-11-14'})['ok']
    offer = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'offers')
    assert offer['attributes']['location_id'] != offer['attributes']['asset_id']
    assert game.replay().get_world() == game.get_world()


def test_real_cli_replays_requested_path_and_persists_it(tmp_path):
    import subprocess
    import sys
    from game import Game
    path = tmp_path / 'funding-and-beds.sqlite'
    result = subprocess.run([sys.executable, '-m', 'game', '--db', str(path), 'play', 'hube-stop-01', '--hot-seat'],
                            input=funding_and_beds_input(), text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'ACCOMMODATION ✓' in result.stdout
    saved = Game.load(path)
    assert saved.project_need('rel_007')['verified'] == 2
    assert saved.project('now')['total'] == 6
    assert saved.project('now')['satisfied'] == 3
    assert saved.replay().get_world() == saved.get_world()


def test_requested_path_is_locale_independent():
    from game.play import run_play
    worlds = []
    for locale in ('en', 'it'):
        game, output = load_fixture(), StringIO()
        run_play(game, StringIO(funding_and_beds_input()), output, locale=locale, hot_seat=True)
        worlds.append(game.get_world())
        if locale == 'it':
            assert 'ALTRI BISOGNI SCOPERTI GIOCANDO' in output.getvalue()
            assert '2 / 2 posto letto assicurati.' in output.getvalue()
    assert worlds[0] == worlds[1]


def test_allocated_capacity_is_not_displayed_as_available_for_another_need():
    from test_engine import complete
    game = load_fixture()
    complete(game, 'resource_005', 'bed', 'person_004', 'beds', quantity=2)
    assert game.submit({'key': 'need', 'kind': 'need', 'actor': 'person_001', 'resource_id': 'resource_005',
                        'quantity': 2, 'unit': 'bed', 'location_id': 'place_001',
                        'available_from': '2026-11-14', 'available_until': '2026-11-14'})['ok']
    demand = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'needs')
    assert game.project_need(demand['id'])['offered'] == 0
    assert game.project_need('rel_007')['offered'] == 2
