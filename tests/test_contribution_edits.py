"""Contribution authorisation and provenance through the public game API."""

from game import Game, load_fixture


def submit(game, kind, key, actor='person_001', **payload):
    return game.submit({'kind': kind, 'key': key, 'actor': actor, **payload})


def offer(game, **payload):
    data = {'resource_id': 'resource_005', 'quantity': 2, 'unit': 'bed',
            'location_id': 'place_001', 'available_from': '2026-11-14',
            'available_until': '2026-11-14', **payload}
    outcome = submit(game, 'offer', 'offer', **data)
    assert outcome['ok'], outcome
    return next(row['entity_id'] for row in outcome['mutations'] if row['entity_type'] == 'relation')


def test_place_correction_preserves_identity_and_old_history(tmp_path):
    game = load_fixture()
    observed = submit(game, 'observe', 'discover', node_kind='place', label='Le Grand Jey')
    place = next(row['entity_id'] for row in observed['mutations'] if row['entity_type'] == 'node')
    before = game.get_world(), game.project('log')
    assert submit(game, 'rename_place', 'other', 'person_002', subject=place,
                  label='Le Grand Jeu')['errors'] == ['owner_required']
    assert submit(game, 'rename_place', 'duplicate', subject=place,
                  label=' Bologna ')['errors'] == ['place_already_exists']
    assert (game.get_world(), game.project('log')) == before
    assert submit(game, 'rename_place', 'correct', subject=place, label='Le Grand Jeu')['ok']
    database = tmp_path / 'rename.sqlite'
    game.save(database)
    saved = Game.load(database)
    assert saved.project('world', at=2)['nodes'][place]['label'] == 'Le Grand Jey'
    assert saved.get_world()['nodes'][place]['label'] == 'Le Grand Jeu'
    assert [n['id'] for n in saved.project('places') if n['label'] == 'Le Grand Jeu'] == [place]
    assert saved.get_world() == saved.replay().get_world()


def test_author_can_edit_free_capacity_but_active_allocation_blocks_it():
    game = load_fixture()
    relation = offer(game)
    assert submit(game, 'amend_capacity', 'amend', subject=relation, quantity=3)['ok']
    assert game.get_world()['relations'][relation]['attributes']['quantity'] == 3
    assert game.project('world', at=2)['relations'][relation]['attributes']['quantity'] == 2
    move = game.derive_possibilities()[0]
    assert submit(game, 'act', 'allocate', 'person_002', possibility_id=move['id'])['ok']
    before = game.get_world(), game.project('log')
    assert submit(game, 'amend_capacity', 'too-late', subject=relation,
                  quantity=1)['errors'] == ['capacity_has_dependencies']
    assert (game.get_world(), game.project('log')) == before
    assert submit(game, 'withdraw', 'withdraw', subject=relation, reason='Unavailable')['ok']
    assert game.get_world()['relations'][relation]['status'] == 'withdrawn'
    assert game.replay().get_world() == game.get_world()
