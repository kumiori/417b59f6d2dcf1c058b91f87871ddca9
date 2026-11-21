"""Regressions exercised through commands, saves and the real terminal."""

from io import StringIO

import pytest

from game import Game, load_fixture
from game.mission_terminal import run_mission


def submit(game, kind, key, *, actor='person_001', **payload):
    return game.submit({'kind': kind, 'key': key, 'actor': actor, **payload})


@pytest.mark.parametrize('kind', ['offer', 'need', 'respond'])
@pytest.mark.parametrize('asset', ['person_002', 'missing', 'place_001', 'object'])
def test_incompatible_venue_assets_are_rejected_atomically(kind, asset):
    game = load_fixture()
    assert submit(game, 'observe', 'observe-object', node_kind='object', label='A camera')['ok']
    if asset == 'object':
        asset = next(node['id'] for node in game.get_world()['nodes'].values()
                     if node['label'] == 'A camera')
    if kind == 'respond':
        request = submit(game, 'request', 'request', actor='person_002',
                         recipient_id='person_001', demand_id='rel_005')
        assert request['ok'], request
        subject = next(m['entity_id'] for m in request['mutations']
                       if m['entity_type'] == 'relation')
        payload = {'subject': subject, 'response': 'modify', 'asset_id': asset}
    else:
        payload = {'resource_id': 'resource_003', 'quantity': 1, 'unit': 'venue',
                   'location_id': 'place_001', 'available_from': '2026-11-14',
                   'available_until': '2026-11-14', 'asset_id': asset}

    before = game.get_world(), game.project('log')
    assert submit(game, kind, 'invalid', **payload)['errors'] == ['invalid_asset']
    assert (game.get_world(), game.project('log')) == before

    assert submit(game, 'observe', 'observe-place', node_kind='place', label='A hall')['ok']
    place = next(node['id'] for node in game.project('places') if node['label'] == 'A hall')
    assert submit(game, kind, 'valid', **{**payload, 'asset_id': place})['ok']


@pytest.mark.parametrize('changed_quantity', [True, 1.0])
def test_retry_preserves_command_value_types_after_save(tmp_path, changed_quantity):
    game = load_fixture()
    command = {'kind': 'offer', 'key': 'bed', 'actor': 'person_001',
               'resource_id': 'resource_005', 'quantity': 1, 'unit': 'bed',
               'location_id': 'place_001', 'available_from': '2026-11-14',
               'available_until': '2026-11-14'}
    result = game.submit(command)
    assert result['ok']
    database = tmp_path / 'storage.sqlite'
    game.save(database)
    for session in (game, Game.load(database)):
        before = session.get_world(), session.project('log')
        assert session.submit(dict(reversed(tuple(command.items())))) == result
        assert session.submit({**command, 'quantity': changed_quantity})['errors'] == ['key_conflict']
        assert (session.get_world(), session.project('log')) == before


def declaration(text, **fields):
    return {'status': 'shared', 'direction': 'offer', 'categories': [], 'description': text, **fields}


def test_projection_orders_declarations_by_original_batch_position(tmp_path):
    game = load_fixture()
    descriptions = [f'Offer {number}' for number in range(1, 11)]
    assert submit(game, 'edit_declarations', 'batch',
                  changes=[declaration(text) for text in descriptions])['ok']
    before = game.project('ecosystem')
    assert [entry['description'] for entry in before['declarations']] == descriptions
    database = tmp_path / 'storage.sqlite'
    game.save(database)
    loaded = Game.load(database)
    for restored in (game.replay(), loaded, loaded.replay()):
        assert restored.project('ecosystem') == before
        assert restored.project('ecosystem', at=2) == before


@pytest.mark.parametrize('interest', ['-', 'x' * 161, ' A literal interest '])
def test_piped_offer_edit_preserves_existing_interest(tmp_path, interest):
    game = load_fixture()
    assert submit(game, 'edit_declarations', 'details', changes=[],
                  details={'interests': interest})['ok']
    database = tmp_path / 'storage.sqlite'
    game.save(database)
    loaded = Game.load(database)
    run_mission(loaded, StringIO('3\n1\n1\nStudio\n\n\ny\n0\n'), StringIO(),
                on_change=lambda session: session.save(database))
    saved = Game.load(database)
    assert saved.get_world()['nodes']['person_001']['metadata']['profile'] == {
        'offers': 'Studio', 'interests': interest,
    }
    saved_log = saved.project('log')
    run_mission(saved, StringIO('3\n1\n1\n\n\n\ny\n0\n'), StringIO())
    assert saved.project('log') == saved_log
    assert saved.get_world() == Game.load(database).get_world()


@pytest.mark.parametrize('legacy', [True, False])
def test_equivalent_declaration_text_preserves_revision_and_provenance(tmp_path, legacy):
    game = load_fixture()
    if legacy:
        assert submit(game, 'share_profile', 'first', profile={'offers': 'Photography'})['ok']
    else:
        assert submit(game, 'edit_declarations', 'first',
                      changes=[declaration('Photography')])['ok']
    original, = game.project('ecosystem')['declarations']
    identity = {'id': original['id'], 'revision': 1}
    if legacy:
        result = submit(game, 'share_profile', 'equivalent', profile={'offers': ' Photography '})
    else:
        result = submit(game, 'edit_declarations', 'equivalent',
                        changes=[declaration(' Photography ', **identity)])
    assert result['ok']
    database = tmp_path / 'storage.sqlite'
    game.save(database)
    restored = Game.load(database)
    assert restored.project('ecosystem')['declarations'] == [original]
    assert submit(restored, 'edit_declarations', 'different',
                  changes=[declaration('Film editing', **identity)])['ok']
    revised, = restored.project('ecosystem')['declarations']
    assert revised['revision'] == 2
    assert revised['description'] == 'Film editing'
    assert revised['provenance']['created'] == original['provenance']['created']
    assert revised['provenance']['revised'] != original['provenance']['revised']
