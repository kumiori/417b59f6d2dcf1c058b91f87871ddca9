import json
from game.replay import simulate


def test_journey_follows_verified_support_and_excludes_incidental_observations():
    game, _ = simulate()
    before = game.get_world(), game.project('log')
    trace = game.project_journey('event_001')
    assert trace['reached'] is True
    assert len(trace['requirements']) == 6
    beds = next(r for r in trace['requirements'] if r['label'] == 'Accommodation')
    path = beds['paths'][0]
    assert path['provider_id'] == 'person_004'
    assert [(s['kind'], s['actor_id']) for s in path['steps'] if s['kind'] in {'offered','connected','committed','verified'}] == [
        ('offered','person_004'), ('connected','person_002'), ('committed','person_004'), ('verified','person_003')]
    assert 'Giulia' not in json.dumps(trace['requirements'])
    assert 'action_000002' not in trace['causal_action_ids']
    venue = next(r for r in trace['requirements'] if r['label'] == 'Venue')
    assert any(s['kind'] == 'discovered' and s['record_id'] == 'place_000003' for s in venue['paths'][0]['steps'])
    assert trace['initial']['satisfied'] == 2
    assert trace['final']['satisfied'] == 6
    assert trace['changes']['offers_activated'] == 4
    assert trace['changes']['needs_satisfied'] == 0
    assert game.replay().project_journey('event_001') == trace
    assert (game.get_world(), game.project('log')) == before
    assert not game.project_journey('event_001', at=4)['reached']


def test_request_discovery_and_response_are_in_actual_support_path():
    from game import load_fixture
    from game.player import PlayerSession
    game = load_fixture()
    andres = PlayerSession(game, 'person_002')
    assert andres.submit({'key': 'discover', 'kind': 'observe', 'source_id': 'person_001',
                          'node_kind': 'person', 'label': 'Giulia', 'relation_kind': 'knows'})['ok']
    context = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'knows')
    assert game.join('Giulia', key='join')['ok']
    giulia = PlayerSession(game, context['target_id'])
    assert andres.submit({'key': 'ask', 'kind': 'request', 'recipient_id': giulia.actor,
                          'demand_id': 'rel_007', 'via_relation_id': context['id']})['ok']
    request = giulia.inbox()[0]
    assert giulia.submit({'key': 'reply', 'kind': 'respond', 'subject': request['id'], 'response': 'accept'})['ok']
    p = game.derive_possibilities()[0]
    assert andres.submit({'key': 'connect', 'kind': 'act', 'possibility_id': p['id']})['ok']
    commitment = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'satisfies')
    assert giulia.submit({'key': 'confirm', 'kind': 'confirm', 'subject': commitment['id']})['ok']
    assert PlayerSession(game, 'person_001').submit({'key': 'verify', 'kind': 'verify', 'subject': commitment['id'],
                                                   'evidence_kind': 'player_confirmation', 'reference': 'Two beds confirmed.'})['ok']
    branch = next(b for b in game.project_journey()['requirements'] if b['label'] == 'Accommodation')
    steps = branch['paths'][0]['steps']
    assert [s['kind'] for s in steps] == ['needed', 'discovered', 'observed', 'requested', 'offered', 'connected', 'committed', 'verified']
    assert next(s for s in steps if s['kind'] == 'observed')['source_id'] == 'person_001'
    assert next(s for s in steps if s['kind'] == 'requested')['actor_id'] == 'person_002'
    assert next(s for s in steps if s['kind'] == 'offered')['actor_id'] == giulia.actor
    assert next(s for s in steps if s['kind'] == 'verified')['actor_id'] == 'person_001'
    assert game.replay().project_journey() == game.project_journey()


def test_unverified_and_withdrawn_branches_are_not_claimed_as_winning_support():
    from game import load_fixture
    from test_engine import complete, offer
    game = load_fixture()
    complete(game, 'resource_005', 'bed', 'person_004', 'beds', quantity=2)
    offer_id = next(r['id'] for r in game.get_world()['relations'].values() if r['kind'] == 'offers')
    assert game.submit({'key': 'withdraw', 'kind': 'withdraw', 'actor': 'person_004', 'subject': offer_id, 'reason': 'Unavailable'})['ok']
    trace = game.project_journey()
    assert not next(r for r in trace['requirements'] if r['label'] == 'Accommodation')['paths']
    assert offer_id not in trace['causal_relation_ids']
    offer(game, 'resource_005', 'person_001', 'replacement', quantity=2)
    assert not next(r for r in game.project_journey()['requirements'] if r['label'] == 'Accommodation')['paths']


def test_recap_is_derived_and_read_only():
    from io import StringIO
    from game.recap import offer_recap
    game, _ = simulate()
    before = game.project('log')
    output = StringIO()
    offer_recap(game, StringIO('y\n'), output)
    text = output.getvalue()
    assert 'HOW THIS BECAME FEASIBLE' in text
    assert 'Andres: connected' in text
    assert 'Editor: verified' in text
    assert 'Date → needed' in text
    assert 'Date → already verified' not in text
    assert game.project('log') == before
    output = StringIO()
    offer_recap(game, StringIO('n\n'), output)
    assert 'HOW THIS BECAME FEASIBLE' not in output.getvalue()
