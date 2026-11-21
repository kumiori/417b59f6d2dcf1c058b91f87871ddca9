from game import load_fixture


def test_load_initial_world():
    game = load_fixture()
    world = game.get_world()
    assert world['nodes']['event_001']['metadata']['feasibility'] == 'hypothetical'
    assert len(world['requirements']) == 6
    assert sum(r['status'] == 'satisfied' for r in world['requirements'].values()) == 2
    assert world['nodes']['person_001']['label'] == 'Marco'
    assert len(game.project('people')) == 4


def test_project_initial_state_and_replay():
    game = load_fixture()
    assert game.project('now')['satisfied'] == 2
    assert game.project('now')['total'] == 6
    assert not game.project('now')['feasible']
    assert game.replay().get_world() == game.get_world()
    assert game.world_at(event=0)['nodes'] == {}
    assert game.world_at(event=1) == game.get_world()
    assert game.world_at(time=game.project('log')[0]['occurred_at']) == game.get_world()


def test_observation_extends_world_and_creates_reported_relation():
    game = load_fixture()
    before = game.get_world()
    command = {'key': 'observation-1', 'kind': 'observe', 'actor': 'person_001',
               'node_kind': 'person', 'label': 'Giulia', 'relation_kind': 'knows'}
    assert game.validate(command) == []
    assert game.get_world() == before
    result = game.submit(command)
    assert result['ok']
    giulia = next(n for n in game.project('people') if n['label'] == 'Giulia')
    relation = next(r for r in game.get_world()['relations'].values() if r['target_id'] == giulia['id'])
    assert relation['kind'] == 'knows'
    assert relation['status'] == 'reported'
    assert relation['source_id'] == 'person_001'
    assert game.submit(command) == result
    assert len(game.project('log')) == 2
    assert game.replay().get_world() == game.get_world()


def offer(game, resource='resource_005', actor='person_004', key='offer', **overrides):
    command = {'key': key, 'kind': 'offer', 'actor': actor, 'resource_id': resource,
               'quantity': 2, 'unit': 'bed', 'location_id': 'place_001',
               'available_from': '2026-11-14', 'available_until': '2026-11-14'}
    command.update(overrides)
    result = game.submit(command)
    assert result['ok'], result
    return result


def test_capacity_and_need_derive_possibility_without_mutation():
    game = load_fixture()
    offer(game)
    result = game.submit({'key': 'need', 'kind': 'need', 'actor': 'person_001',
                          'resource_id': 'resource_005', 'quantity': 1, 'unit': 'bed',
                          'location_id': 'place_001', 'available_from': '2026-11-14',
                          'available_until': '2026-11-14'})
    assert result['ok']
    before, log = game.get_world(), game.project('log')
    possibilities = game.derive_possibilities()
    assert len(possibilities) == 2
    assert {p['reason']['code'] for p in possibilities} == {'need_offer_match'}
    assert game.get_world() == before
    assert game.project('log') == log
    assert not game.project('now')['feasible']


def test_new_resource_can_be_offered_and_requested():
    game = load_fixture()
    offer(game, resource=None, resource_label='Screen printing', unit='hour')
    resource = next(n for n in game.project('resources') if n['label'] == 'Screen printing')
    result = game.submit({'key': 'new-need', 'kind': 'need', 'actor': 'person_001',
                          'resource_id': resource['id'], 'quantity': 1, 'unit': 'hour',
                          'location_id': 'place_001', 'available_from': '2026-11-14',
                          'available_until': '2026-11-14'})
    assert result['ok']
    assert len(game.derive_possibilities()) == 1


def pending_accommodation(game):
    offer(game)
    possibility = game.derive_possibilities()[0]
    result = game.submit({'key': 'act', 'kind': 'act', 'actor': 'person_002', 'possibility_id': possibility['id']})
    assert result['ok'], result
    commitment = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'satisfies')
    return commitment['id'], result['action_id']


def test_act_requires_provider_confirmation_then_independent_verification():
    game = load_fixture()
    cid, aid = pending_accommodation(game)
    assert game.get_world()['relations'][cid]['status'] == 'proposed'
    assert game.get_world()['actions'][aid]['status'] == 'proposed'
    assert game.project('now')['satisfied'] == 2
    assert game.submit({'key': 'confirm', 'kind': 'confirm', 'actor': 'person_004', 'subject': cid})['ok']
    assert game.get_world()['relations'][cid]['status'] == 'committed'
    assert game.get_world()['actions'][aid]['status'] == 'awaiting_verification'
    assert game.project('now')['satisfied'] == 2
    result = game.verify(cid, actor='person_003', key='verify', evidence_kind='player_confirmation',
                         reference='Player X confirmed two beds on the proposed date.')
    assert result['ok'], result
    assert game.get_world()['relations'][cid]['status'] == 'verified'
    assert game.get_world()['actions'][aid]['status'] == 'verified'
    req = game.get_world()['requirements']['requirement_005']
    assert req['status'] == 'satisfied'
    assert req['satisfied_by'] == [cid]
    assert game.project('now')['satisfied'] == 3
    assert game.evaluate_requirements()['requirement_005']['status'] == 'satisfied'
    assert game.replay().get_world() == game.get_world()


def complete(game, resource, unit, actor, key, quantity=1):
    extra = {}
    if resource == 'resource_003':
        assert game.submit({'key': key+'-place', 'kind': 'observe', 'actor': actor,
                            'node_kind': 'place', 'label': 'Sala Comune'})['ok']
        extra['asset_id'] = next(n['id'] for n in game.project('places') if n['label'] == 'Sala Comune')
    offer(game, resource, actor, key+'-offer', quantity=quantity, unit=unit, **extra)
    possibility = next(p for p in game.derive_possibilities()
                       if game.get_world()['relations'][p['source_ids'][0]]['target_id'] == resource)
    result = game.submit({'key': key+'-act', 'kind': 'act', 'actor': 'person_002', 'possibility_id': possibility['id']})
    assert result['ok'], result
    commitment = next(r for r in game.get_world()['relations'].values()
                      if r['kind'] == 'satisfies' and r['attributes']['action_id'] == result['action_id'])
    assert game.submit({'key': key+'-confirm', 'kind': 'confirm', 'actor': actor, 'subject': commitment['id']})['ok']
    result = game.verify(commitment['id'], actor='person_003' if actor != 'person_003' else 'person_001',
                         key=key+'-verify', evidence_kind='player_confirmation', reference='Fictional confirmation for scenario.')
    assert result['ok'], result


def test_all_requirements_cross_threshold_and_log_transition():
    game = load_fixture()
    complete(game, 'resource_003', 'venue', 'person_004', 'venue')
    complete(game, 'resource_004', 'confirmation', 'person_002', 'date')
    complete(game, 'resource_005', 'bed', 'person_004', 'beds', quantity=2)
    assert game.project('now')['satisfied'] == 5
    before_final = len(game.project('log'))
    complete(game, 'resource_006', 'commitment', 'person_003', 'documentation')
    assert game.project('now')['feasible']
    assert game.get_world()['nodes']['event_001']['metadata']['feasibility'] == 'feasible'
    assert game.project('log')[-1]['kind'] == 'event.feasible'
    assert not game.project('now', at=before_final)['feasible']
    assert game.replay().get_world() == game.get_world()
    assert not game.submit({'key': 'late', 'kind': 'observe', 'actor': 'person_001', 'node_kind': 'person', 'label': 'Late'})['ok']


def test_invalid_commands_are_atomic_and_retries_survive_replay():
    game = load_fixture()
    cid, _ = pending_accommodation(game)
    invalid = [
        {'key': 'bad', 'kind': 'confirm', 'actor': 'person_002', 'subject': cid},
        {'key': 'bad', 'kind': 'verify', 'actor': 'person_003', 'subject': cid,
         'evidence_kind': 'player_confirmation', 'reference': 'Too early'},
        {'key': 'bad', 'kind': 'offer', 'actor': 'person_004', 'resource_label': 'New resource',
         'quantity': -1, 'unit': 'bed', 'location_id': 'place_001',
         'available_from': '2026-11-14', 'available_until': '2026-11-14'},
        {'key': 'bad', 'kind': 'act', 'actor': 'person_002', 'possibility_id': 'match:rel_007:rel_000002'},
        {'key': 'bad', 'kind': 'observe', 'actor': 'person_001', 'target_id': 'missing'},
    ]
    before, log = game.get_world(), game.project('log')
    for command in invalid:
        assert not game.apply(command)['ok']
        assert game.get_world() == before
        assert game.project('log') == log
    command = {'key': 'confirm', 'kind': 'confirm', 'actor': 'person_004', 'subject': cid}
    result = game.submit(command)
    replay = game.replay()
    assert replay.submit(command) == result
    assert not replay.submit({**command, 'actor': 'person_002'})['ok']
    assert not game.verify(cid, actor='person_004', key='self', evidence_kind='player_confirmation', reference='Self')['ok']
    assert not game.verify(cid, actor='person_003', key='self-report', evidence_kind='self_report', reference='Self')['ok']


def test_incompatible_capacity_does_not_match():
    for overrides in ({'unit': 'person'}, {'available_from': '2026-11-15', 'available_until': '2026-11-16'}):
        game = load_fixture()
        offer(game, **overrides)
        assert game.derive_possibilities() == []


def test_partial_capacity_and_no_double_allocation():
    game = load_fixture()
    complete(game, 'resource_005', 'bed', 'person_004', 'one-bed', quantity=1)
    assert game.get_world()['requirements']['requirement_005']['status'] == 'partially_satisfied'
    assert game.derive_possibilities() == []
    complete(game, 'resource_005', 'bed', 'person_001', 'other-bed', quantity=1)
    assert game.get_world()['requirements']['requirement_005']['status'] == 'satisfied'


def test_proposition_is_open_content_and_withdrawal_releases_capacity():
    game = load_fixture()
    assert game.submit({'key': 'proposal', 'kind': 'propose', 'actor': 'person_001', 'label': 'An improvised reading'})['ok']
    assert any(n['label'] == 'An improvised reading' for n in game.project('network')['nodes'])
    cid, _ = pending_accommodation(game)
    assert game.submit({'key': 'withdraw', 'kind': 'withdraw', 'actor': 'person_004', 'subject': cid, 'reason': 'Unavailable'})['ok']
    assert game.get_world()['relations'][cid]['status'] == 'withdrawn'
    assert len(game.derive_possibilities()) == 1
    assert game.project('now')['satisfied'] == 2


def test_persistent_log_rebuilds_world_and_detects_stale_writer(tmp_path):
    from game import Game
    import pytest
    path = tmp_path / 'world.sqlite'
    game = load_fixture()
    game.save(path)
    stale = Game.load(path)
    cid, _ = pending_accommodation(game)
    game.save(path)
    restored = Game.load(path)
    assert restored.get_world() == game.get_world()
    assert restored.project('log') == game.project('log')
    assert restored.world_at(event=1) == load_fixture().get_world()
    assert stale.submit({'key': 'other', 'kind': 'propose', 'actor': 'person_001', 'label': 'Other'})['ok']
    with pytest.raises(ValueError, match='log_conflict'):
        stale.save(path)
    assert Game.load(path).get_world() == game.get_world()


def test_replay_rejects_corrupt_mutation_chain():
    from game import Game
    import pytest
    game = load_fixture()
    pending_accommodation(game)
    entries = game.project('log')
    entries[-1]['mutations'][0]['before'] = {'forged': True}
    with pytest.raises(ValueError, match='invalid_mutation_chain'):
        Game.from_log(entries)


def test_venue_requires_a_concrete_place():
    game = load_fixture()
    result = game.submit({'key': 'venue', 'kind': 'offer', 'actor': 'person_004',
                         'resource_id': 'resource_003', 'quantity': 1, 'unit': 'venue',
                         'location_id': 'place_001', 'available_from': '2026-11-14',
                         'available_until': '2026-11-14'})
    assert result['ok']
    assert game.derive_possibilities() == []
    assert game.submit({'key': 'place', 'kind': 'observe', 'actor': 'person_004',
                        'node_kind': 'place', 'label': 'Sala Comune', 'relation_kind': 'suggests'})['ok']
    place = next(n for n in game.project('places') if n['label'] == 'Sala Comune')
    offer(game, 'resource_003', 'person_004', 'specific-venue', unit='venue', quantity=1, asset_id=place['id'])
    assert len(game.derive_possibilities()) == 1


def test_unsupported_fields_are_not_silently_ignored_and_dates_normalize():
    game = load_fixture()
    before = game.get_world()
    result = game.submit({'key': 'private', 'kind': 'observe', 'actor': 'person_001',
                          'label': 'Private person', 'node_kind': 'person', 'visibility': 'private'})
    assert not result['ok']
    assert game.get_world() == before
    offer(game, available_from='20261114', available_until='20261114')
    assert len(game.derive_possibilities()) == 1
    assert game.get_world()['relations']['rel_000002']['attributes']['available_from'] == '2026-11-14'


def test_projection_distinguishes_pending_from_verified_capacity():
    game = load_fixture()
    cid, _ = pending_accommodation(game)
    game.submit({'key': 'confirm', 'kind': 'confirm', 'actor': 'person_004', 'subject': cid})
    requirement = next(r for r in game.project('now')['requirements'] if r['id'] == 'requirement_005')
    assert requirement['progress'] == {'verified': 0, 'minimum': 2, 'unit': 'bed', 'pending_status': 'committed'}
    assert requirement['status'] == 'unsatisfied'


def test_withdrawing_verified_offer_reopens_requirement_before_ending():
    game = load_fixture()
    complete(game, 'resource_005', 'bed', 'person_004', 'beds', quantity=2)
    assert game.project('now')['satisfied'] == 3
    supplied = next(r for r in game.get_world()['relations'].values() if r['kind'] == 'offers')
    result = game.submit({'key': 'withdraw-offer', 'kind': 'withdraw', 'actor': 'person_004',
                          'subject': supplied['id'], 'reason': 'No longer available'})
    assert result['ok']
    assert game.project('now')['satisfied'] == 2
    assert game.get_world()['requirements']['requirement_005']['satisfied_by'] == []
    assert game.derive_possibilities() == []
    assert game.project('now', at=5)['satisfied'] == 3
    assert game.replay().get_world() == game.get_world()


def test_historical_time_equals_transaction_and_detached_reads():
    game = load_fixture()
    cid, _ = pending_accommodation(game)
    time = game.project('log')[1]['occurred_at']
    assert game.world_at(time=time) == game.world_at(event=2)
    assert game.project('network', time=time) == game.project('network', at=2)
    world = game.get_world()
    world['nodes'].clear()
    log = game.project('log')
    log[0]['mutations'].clear()
    assert len(game.project('people')) == 4
    assert game.replay().get_world() == game.get_world()
