import json
import subprocess
import sys

from game import Game, load_fixture
from game.missions import mission_proposals
from game.player import PlayerSession


def cli(db, *args, lines=None, command=None):
    prefix = command or [sys.executable, '-m', 'game']
    return subprocess.run(
        [*prefix, '--db', str(db), *args],
        input='\n'.join(lines) + '\n' if lines is not None else None,
        text=True, capture_output=True, timeout=10, check=True,
    ).stdout


def complete_stop(db, command=None):
    first = cli(db, 'play', '--hot-seat', lines=[
        '1',                           # Observe before choosing a player.
        '2', '2', '1',                 # Act as Andres on the venue.
        '1', '1', '1', '', '',         # Offer one venue in Bologna on the event date.
        '1', 'Sala Comune', 'y', 'y',  # Add the venue, connect and confirm.
        '0', '1', '3', '0', '0',       # Observe, see my contributions, and save.
    ], command=command)
    assert 'NON HO MAI IMPARATO' in first
    assert 'Organise the book presentation' in first
    assert 'PROGRESS [■■□□□□] 2 / 6' in first
    assert '[1] OBSERVE ECOSYSTEM' in first and '[2] ACT' in first
    assert 'Gathering: Bologna · 2026-11-14 (proposed)' in first
    for label in ('Books', 'Hube participation', 'Venue', 'Date', 'Accommodation', 'Documentation'):
        assert label in first
    assert 'Offered: 1/1 · committed: 1/1 · verified: 0/1' in first
    saved = Game.load(db)
    assert saved.project('now')['satisfied'] == 2
    commitment = saved.project_need('rel_005')['allocations'][0]
    assert commitment['status'] == 'committed'
    provider = PlayerSession(saved, 'person_002')
    assert provider.submit({
        'key': 'self-verify', 'kind': 'verify', 'subject': commitment['id'],
        'evidence_kind': 'player_confirmation', 'reference': 'Own venue',
    })['errors'] == ['independent_verifier_required']

    lines = ['2', '3']  # Reopen as Editor.

    def verify(note, *, final=False):
        lines.extend(['1', '8', '1', '2', note])
        if not final:
            lines.append('0')

    def offer(quantity='1'):
        lines.extend(['2', '1', '1', quantity, '1', '', '', 'n', 'y', 'y', '0'])

    verify('Venue confirmed.')
    offer()  # Editor supplies the date.
    lines.extend(['s', '1', '2'])
    verify('Date agreed.')
    offer('2')  # Marco supplies accommodation.
    lines.extend(['s', '2', '2'])
    verify('Two beds confirmed.')
    offer()  # Andres supplies documentation.
    lines.extend(['s', '3', '2'])
    verify('Documentation agreed.', final=True)
    lines.extend(['4', '1', '0'])
    resumed = cli(db, 'play', '--hot-seat', lines=lines, command=command)
    assert 'STOP 01 complete. The book presentation can happen.' in resumed
    assert 'PROGRESS [■■■■■■] 6 / 6' in resumed
    assert 'HOW THIS BECAME FEASIBLE' in resumed
    assert 'Gathering: Bologna · 2026-11-14 (verified)' in resumed

    finished = Game.load(db)
    assert finished.project('now')['feasible']
    assert all(r['status'] == 'satisfied' for r in finished.project('now')['requirements'])
    assert finished.replay().get_world() == finished.get_world()
    assert json.loads(cli(db, 'replay', command=command)) == finished.get_world()
    assert json.loads(cli(db, 'journey', '--json', command=command))['reached']


def test_book_presentation_from_first_observation_to_saved_completion(tmp_path):
    complete_stop(tmp_path / 'stop.sqlite')


def test_alias_and_optional_profile_with_explicit_sharing(tmp_path):
    db = tmp_path / 'profile.sqlite'
    cli(db, 'play', lines=[
        '3', '4', 'Ada', '1', 'Private draft', '', '', 'n',
        '3', '1', 'Photography', 'A place to stay', 'Book design', 'y', '0',
    ])
    saved = Game.load(db)
    ada = next(person for person in saved.project('people') if person['label'] == 'Ada')
    profile = {'offers': 'Photography', 'needs': 'A place to stay', 'interests': 'Book design'}
    assert ada['metadata']['profile'] == profile
    assert 'Private draft' not in json.dumps(saved.project('log'))
    assert not any(relation['kind'] == 'offers' for relation in saved.get_world()['relations'].values())
    assert saved.project('now')['satisfied'] == 2
    assert saved.replay().get_world() == saved.get_world()

    session = PlayerSession(saved, 'person_001')
    assert session.submit({'key': 'spoof', 'kind': 'share_profile', 'actor': ada['id'], 'profile': {}})['errors'] == ['actor_mismatch']
    assert session.submit({'key': 'target', 'kind': 'share_profile', 'target_id': ada['id'], 'profile': {}})['errors'] == ['unsupported_field']
    assert session.submit({'key': 'invalid', 'kind': 'share_profile', 'profile': {'offers': 'x' * 161}})['errors'] == ['invalid_profile']
    assert 'profile' not in saved.get_world()['nodes']['person_001']['metadata']

    reopened = cli(db, 'play', lines=['1', '3', '6', '1', '-', '', '', 'y', '1', '0'])
    assert 'I can offer: Photography' in reopened
    assert reopened.count('I can offer: Photography') == 2  # Initial Observe and My Contributions.
    assert 'Private draft' not in reopened
    assert Game.load(db).get_world()['nodes'][ada['id']]['metadata']['profile'] == {
        'needs': 'A place to stay', 'interests': 'Book design',
    }


def test_proposer_receives_detached_context_and_can_only_select_validated_ids():
    game = load_fixture()
    session = PlayerSession(game, 'person_002')
    assert session.submit({'key': 'profile', 'kind': 'share_profile',
                           'profile': {'offers': 'A venue'}})['ok']
    world, log = game.get_world(), game.project('log')
    baseline = mission_proposals(session, 'rel_005')
    assert len(baseline) == 3

    def propose(context):
        assert context.actor_id == 'person_002'
        assert context.demand_id == 'rel_005'
        assert context.profile == {'offers': 'A venue'}
        assert context.world == world
        context.world['nodes'].clear()
        context.profile.clear()
        move = context.candidates[-1]
        move['suggested_commands'][0]['kind'] = 'verify'
        return ['made-up-action', move['id'], move['id']]

    assert mission_proposals(session, 'rel_005', propose) == [baseline[-1]]

    def unavailable(context):
        raise TimeoutError('proposer unavailable')

    assert mission_proposals(session, 'rel_005', unavailable) == baseline
    assert mission_proposals(session, 'rel_005', lambda context: ['invented']) == baseline
    assert game.get_world() == world
    assert game.project('log') == log


def test_book_menu_uses_italian_catalog(tmp_path):
    output = cli(tmp_path / 'italian.sqlite', '--locale', 'it', 'play', lines=['1', '0'])
    assert 'Un libro cerca un incontro.' in output
    assert 'PROGRESSO [■■□□□□] 2 / 6' in output
    assert 'Partecipazione di Hube' in output
