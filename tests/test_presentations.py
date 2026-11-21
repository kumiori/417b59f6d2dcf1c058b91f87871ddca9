"""Candidate boundaries and local invitation redemption via recorded commands."""

from game import Game, load_fixture
from game.context_requests import invitation_for, token_digest
from game.presentations import candidate_is_feasible, candidate_progress


def submit(game, kind, key, *, actor='person_001', **payload):
    return game.submit({'kind': kind, 'key': key, 'actor': actor, **payload})


def new_candidate(game, date, city, venue):
    result = submit(
        game, 'propose_presentation', city, date=date, city=city, venue=venue
    )
    assert result['ok'], result
    return next(
        m['entity_id'] for m in result['mutations'] if m['entity_type'] == 'node'
    )


def verified_support(game, subject, requirement_id, key, quantity=1):
    result = submit(
        game,
        'offer_to_presentation',
        key,
        subject=subject,
        requirement_id=requirement_id,
        quantity=quantity,
        detail='Committed locally',
    )
    assert result['ok'], result
    payload = {'subject': subject, 'contribution_id': result['action_id']}
    assert submit(game, 'confirm_presentation_offer', key + '-confirm', **payload)['ok']
    before = game.get_world(), game.project('log')
    assert submit(
        game, 'verify_presentation_offer', key + '-self', reference='Saw it', **payload
    )['errors'] == [
        'independent_verifier_required',
    ]
    assert (game.get_world(), game.project('log')) == before
    assert submit(
        game,
        'verify_presentation_offer',
        key + '-verify',
        actor='person_002',
        reference='Saw it',
        **payload,
    )['ok']
    return result['action_id']


def test_verified_support_never_counts_towards_a_different_presentation(tmp_path):
    game = load_fixture()
    paris = new_candidate(game, '2027-01-15', 'Paris', 'Le Grand Jeu')
    bologna = new_candidate(game, '2027-02-22', 'Bologna', 'Sala Comune')
    paris_support = verified_support(game, paris, 'requirement_003', 'paris-venue')
    verified_support(game, bologna, 'requirement_004', 'bologna-date')
    assert submit(
        game,
        'confirm_presentation_offer',
        'wrong-presentation',
        subject=bologna,
        contribution_id=paris_support,
    )['errors'] == ['invalid_subject']
    world = game.get_world()
    for candidate, requirements in (
        (paris, ['requirement_003']),
        (bologna, ['requirement_004']),
    ):
        node = world['nodes'][candidate]
        assert [
            r.id for r, quantity in candidate_progress(world, node) if quantity
        ] == requirements
        assert not candidate_is_feasible(world, node)

    for suffix in (1, 2, 4, 5, 6):
        verified_support(
            game,
            paris,
            f'requirement_{suffix:03d}',
            f'paris-{suffix}',
            quantity=2 if suffix == 5 else 1,
        )
    assert game.project('log')[-1]['kind'] == 'presentation.feasible'
    assert game.project('now')['satisfied'] == 2
    world = game.get_world()
    assert candidate_is_feasible(world, world['nodes'][paris])
    assert not candidate_is_feasible(world, world['nodes'][bologna])
    database = tmp_path / 'presentations.sqlite'
    game.save(database)
    assert Game.load(database).replay().get_world() == world


def test_local_invitation_preserves_request_context_until_explicit_response(tmp_path):
    game = load_fixture()
    paris = new_candidate(game, '2027-01-15', 'Paris', 'Le Grand Jeu')
    token = 'test-one-use-invitation'
    result = submit(
        game,
        'create_context_request',
        'invite',
        subject=paris,
        question='Could Le Grand Jeu host the book?',
        invite_digest=token_digest(token),
    )
    assert result['ok'], result
    database = tmp_path / 'invitation.sqlite'
    game.save(database)
    saved = Game.load(database)
    world = saved.get_world()
    invite = invitation_for(world, token)
    request = invite['metadata']['context_request']
    assert request['subject'] == paris
    assert request['inviter'] == 'person_001'
    assert request['status'] == 'open'
    assert not world['nodes'][paris]['metadata']['contributions']
    assert token not in str(saved.project('log'))
    accepted = saved.join('Camille', key='join')
    actor = next(
        m['entity_id'] for m in accepted['mutations'] if m['entity_type'] == 'node'
    )
    before = saved.get_world(), saved.project('log')
    payload = {'subject': invite['id'], 'response': 'help'}
    assert submit(
        saved, 'respond_context_request', 'wrong', actor=actor, token='wrong', **payload
    )['errors'] == ['invalid_invitation']
    assert (saved.get_world(), saved.project('log')) == before
    assert submit(
        saved, 'respond_context_request', 'answer', actor=actor, token=token, **payload
    )['ok']
    world = saved.get_world()
    assert invitation_for(world, token) is None
    assert (
        world['nodes'][invite['id']]['metadata']['context_request']['responder']
        == actor
    )
    assert not world['nodes'][paris]['metadata']['contributions']
    assert saved.replay().get_world() == world
