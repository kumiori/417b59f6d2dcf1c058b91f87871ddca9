from io import StringIO
import json
import subprocess
import sys

from game import Game, load_fixture
from game.declarations import actor_declarations, taxonomy
from game.mission_terminal import run_mission
from game.player import PlayerSession
from game_gamer_semantics import Taxonomy, project_ecosystem
from game_gamer_semantics.assistant import suggested_keys


def declaration(direction, description, *categories):
    return {'direction': direction, 'description': description, 'categories': list(categories), 'status': 'shared'}


def edit(game, actor, key, *changes, **details):
    return PlayerSession(game, actor).submit({
        'kind': 'edit_declarations', 'key': key, 'changes': list(changes), 'details': details,
    })


def test_directed_matrices_and_coverage_use_shared_categories_once_per_pair():
    game = load_fixture()
    assert edit(game, 'person_001', 'write-1',
                declaration('offer', 'Photography and AV', 'technical', 'creative'),
                declaration('offer', 'Editing', 'creative'),
                declaration('need', 'Audio support', 'technical'))['ok']
    assert edit(game, 'person_002', 'write-2',
                declaration('need', 'Photo and sound', 'creative', 'technical'),
                declaration('need', 'A loan', 'financial'),
                declaration('need', 'Something unexpected'),
                declaration('offer', 'Poster printing', 'material'))['ok']
    assert edit(game, 'person_003', 'write-3', declaration('need', 'A projector', 'technical'),
                declaration('need', 'Poster printing', 'material'))['ok']

    view = game.project('ecosystem')
    assert tuple(view['categories']) == taxonomy().keys
    assert view['offer_matrix']['person_001']['creative'] == 2
    assert view['need_matrix']['person_002']['technical'] == 1
    assert view['coverage']['creative'] == {
        'offering_players': 1, 'seeking_players': 1, 'offer_declarations': 2, 'need_declarations': 1,
    }
    assert view['potential_matrix']['person_001'] == {
        'person_001': 0, 'person_002': 2, 'person_003': 1, 'person_004': 0,
    }
    assert view['potential_matrix']['person_002']['person_001'] == 0
    assert [row['description'] for row in view['uncategorized']] == ['Something unexpected']
    assert {row['declaration']['description']: row['reason'] for row in view['unmatched_needs']} == {
        'Audio support': 'no_interpersonal_offer',
        'A loan': 'no_interpersonal_offer',
        'Something unexpected': 'uncategorized',
    }
    view['declarations'][0]['categories'].clear()
    assert game.project('ecosystem')['declarations'][0]['categories'] == ['creative', 'technical']
    assert game.project('now')['satisfied'] == 2
    assert not game.derive_possibilities()


def test_empty_and_private_ecosystems():
    assert Game().project('ecosystem')['potential_matrix'] == {}
    assert all(count == 0 for row in load_fixture().project('ecosystem')['potential_matrix'].values()
               for count in row.values())
    records = [dict(declaration('offer', 'Secret', 'creative'), actor_id='a', status=status)
               for status in ('private', 'withdrawn')]
    records.append(dict(declaration('need', 'Photo', 'creative'), actor_id='b'))
    view = project_ecosystem(['a', 'b'], records, taxonomy())
    assert view['potential_matrix']['a']['b'] == 0
    assert [row['description'] for row in view['declarations']] == ['Photo']


def test_legacy_declarations_can_be_revised_with_provenance_and_withdrawn(tmp_path):
    game = load_fixture()
    actor = 'person_001'
    session = PlayerSession(game, actor)
    assert session.submit({'kind': 'share_profile', 'key': 'old', 'profile': {
        'offers': 'Photography', 'needs': 'Venue', 'interests': 'Books',
    }})['ok']
    legacy = game.project('ecosystem', at=2)['uncategorized']
    assert {row['description'] for row in legacy} == {'Photography', 'Venue'}
    original = next(row for row in legacy if row['direction'] == 'offer')
    identifier = original['id']
    assert original['provenance']['created']['action_id'] == 'action_000002'
    change = dict(declaration('offer', 'Photography,  vidéo', 'creative', 'technical'),
                  id=identifier, revision=1)
    assert edit(game, actor, 'revise', change, capabilities='Camera operation')['ok']
    record = actor_declarations(game.get_world(), actor)[identifier]
    assert record['revision'] == 2 and record['description'] == 'Photography,  vidéo'
    assert record['taxonomy_version'] == 'hube/1'
    assert record['provenance']['created'] == original['provenance']['created']
    assert record['provenance']['revised']['action_id'] == 'action_000003'
    assert edit(game, actor, 'revise', change, capabilities='Camera operation')['ok']  # Exact retry.
    assert edit(game, actor, 'stale', change)['errors'] == ['stale_declaration']
    assert edit(game, 'person_002', 'spoof', dict(change, revision=2))['errors'] == ['invalid_declaration']
    assert edit(game, actor, 'withdraw', {'id': identifier, 'revision': 2, 'status': 'withdrawn'})['ok']
    assert edit(game, actor, 'revive', dict(change, revision=3))['errors'] == ['invalid_declaration']
    db = tmp_path / 'profile.sqlite'
    game.save(db)
    loaded = Game.load(db)
    assert loaded.get_world() == loaded.replay().get_world() == game.get_world()
    assert loaded.project('ecosystem') == game.project('ecosystem')
    assert [row['description'] for row in loaded.project('ecosystem')['declarations']] == ['Venue']
    assert loaded.project('people')[0]['metadata']['profile'] == {
        'needs': 'Venue', 'interests': 'Books', 'capabilities': 'Camera operation',
    }
    assert loaded.project('ecosystem', at=2) == game.project('ecosystem', at=2)
    cli = subprocess.check_output([sys.executable, '-m', 'game', '--db', str(db), 'ecosystem', '--at', 'T3'])
    assert json.loads(cli) == game.project('ecosystem', at=3)


def test_custom_taxonomy_and_atomic_batch_validation(monkeypatch, tmp_path):
    config = tmp_path / 'taxonomy.json'
    config.write_text(json.dumps({'version': 'festival/9', 'categories': {'lighting': 'Lighting'}}))
    monkeypatch.setenv('HUBE_TAXONOMY', str(config))
    assert Taxonomy.from_dict({'version': 'empty', 'categories': {}}).keys == ()
    game = load_fixture()
    start = game.get_world()
    result = edit(game, 'person_001', 'bad', declaration('offer', 'Light', 'lighting'),
                  declaration('offer', 'Space', 'space'))
    assert result['errors'] == ['unknown_category']
    assert game.get_world() == start
    assert edit(game, 'person_001', 'ok', declaration('offer', 'Light', 'lighting'))['ok']
    view = game.project('ecosystem')
    assert view['taxonomy_version'] == 'festival/9'
    assert view['categories'] == {'lighting': 'Lighting'}
    assert view['declarations'][0]['taxonomy_version'] == 'festival/9'
    monkeypatch.delenv('HUBE_TAXONOMY')
    replayed = game.replay()
    assert replayed.project('ecosystem')['declarations'][0]['categories'] == ['lighting']
    assert replayed.project('ecosystem')['offer_matrix']['person_001']['lighting'] == 1


def test_inspection_and_advisor_cannot_submit_a_match_as_an_action():
    game = load_fixture()
    assert edit(game, 'person_001', 'offer', declaration('offer', 'A room', 'space'))['ok']
    assert edit(game, 'person_002', 'need', declaration('need', 'A venue', 'space'))['ok']
    before = game.get_world(), game.project('log')
    context = []

    def assistant(topic, payload):
        context.append(topic)
        payload['connections'].clear()
        return ['invented→actor', 'person_001→person_002']

    output = StringIO()
    # Open the connection, ask to see actions as Editor, select introduction, decline.
    run_mission(game, StringIO('5\n1\ny\n3\n1\nn\n0\n'), output, semantic_assistant=assistant)
    assert context == ['connections']
    for fragment in ('Marco → Andres', 'A room', 'A venue', 'Related mission condition: Venue',
                     'Introduce these players'):
        assert fragment in output.getvalue()
    assert before == (game.get_world(), game.project('log'))
    assert not PlayerSession(game, 'person_002').submit({
        'key': 'force', 'kind': 'act', 'possibility_id': 'person_001→person_002',
    })['ok']
    assert before == (game.get_world(), game.project('log'))
    assert suggested_keys(lambda *_: ['space', 'bad', 'space'], 'categories', {}, {'space'}) == ['space']
    assert suggested_keys(lambda *_: 1 / 0, 'mission_actions', {}, {'match'}) == []
