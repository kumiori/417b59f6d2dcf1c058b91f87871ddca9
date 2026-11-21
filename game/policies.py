"""Actor eligibility and checks shared by command and read paths."""


def is_playable(world, actor):
    return bool(world['nodes'].get(actor, {}).get('metadata', {}).get('playable'))


def authorize_actor(world, command):
    if command['kind'] == 'join':
        if command.get('actor') != 'system':
            raise ValueError('invalid_join')
    elif not is_playable(world, command.get('actor')):
        raise ValueError('unknown_player')


def pending_request(world, actor, recipient, demand_id):
    return any(
        relation['kind'] == 'requested'
        and relation['status'] == 'proposed'
        and relation['source_id'] == actor
        and relation['target_id'] == recipient
        and relation['attributes']['demand_id'] == demand_id
        for relation in world['relations'].values()
    )
