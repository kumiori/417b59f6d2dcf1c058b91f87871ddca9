"""Read models derived from detached Hube world snapshots."""

from .capacity import (
    DEMAND_KINDS,
    active_allocations,
    is_available_offer,
    is_compatible,
    is_open_demand,
    possibilities,
)
from .declarations import ecosystem
from .model import OBSERVATION_KINDS, normalize_label, relation_valid
from .policies import is_playable, pending_request
from .requirements import is_feasible, required_requirements


def derive_player_moves(world, actor, *, demand_id=None, explore=False):
    if not is_playable(world, actor):
        raise ValueError('unknown_player')
    moves = [
        {**match, 'tier': 'grounded'}
        for match in possibilities(world)
        if demand_id is None or match['target_ids'] == [demand_id]
    ]
    if not explore:
        return moves
    if demand_id is None:
        raise ValueError('exploration_requires_one_need')

    demand = world['relations'].get(demand_id)
    if demand and is_open_demand(demand):
        allocated = sum(
            r['attributes']['quantity']
            for r in active_allocations(world)
            if r['attributes']['demand_id'] == demand_id
        )
        if allocated < demand['attributes']['quantity']:
            moves.extend(exploratory_requests(world, actor, demand_id))

    return sorted(
        moves,
        key=lambda move: (
            move['tier'] != 'grounded',
            move['reason']['parameters'].get('context_relation_id') is None,
        ),
    )


def exploratory_requests(world, actor, demand_id):
    for person in world['nodes'].values():
        if person['kind'] != 'person' or person['id'] == actor:
            continue
        recipient = person['id']
        if pending_request(world, actor, recipient, demand_id):
            continue
        context = next(
            (
                relation['id']
                for relation in world['relations'].values()
                if relation['kind'] in {'knows', 'introduced'}
                and relation['target_id'] == recipient
                and relation['status'] not in {'withdrawn', 'rejected'}
            ),
            None,
        )
        command = {'kind': 'request', 'recipient_id': recipient, 'demand_id': demand_id}
        if context:
            command['via_relation_id'] = context
        yield {
            'id': 'ask:' + demand_id + ':' + recipient,
            'kind': 'ask',
            'tier': 'exploratory',
            'source_ids': [recipient],
            'target_ids': [demand_id],
            'reason': {
                'code': 'ask_about_unmet_need',
                'parameters': {'context_relation_id': context},
            },
            'suggested_commands': [command],
        }


def resolve_resources(world, label):
    if not isinstance(label, str):
        raise ValueError('invalid_node')
    matches = []
    for node in world['nodes'].values():
        if node['kind'] == 'resource' and normalize_label(
            node['label']
        ) == normalize_label(label):
            required_by = sorted(
                {
                    r['source_id']
                    for r in world['relations'].values()
                    if r['kind'] == 'requires' and r['target_id'] == node['id']
                }
            )
            matches.append({**node, 'required_by': required_by})
    return sorted(matches, key=lambda node: (not node['required_by'], node['id']))


def valid_observation_relations(world, source_id, target_id):
    source, target = world['nodes'][source_id], world['nodes'][target_id]
    return [
        kind
        for kind in OBSERVATION_KINDS
        if relation_valid(kind, source['kind'], target['kind'])
    ]


def project_need(world, demand_id):
    demand = world['relations'].get(demand_id)
    if not demand or demand['kind'] not in DEMAND_KINDS:
        raise ValueError('invalid_demand')
    offers = []
    active = active_allocations(world)
    for offer in world['relations'].values():
        if not is_available_offer(offer) or offer['target_id'] != demand['target_id']:
            continue
        used_elsewhere = sum(
            r['attributes']['quantity']
            for r in active
            if r['attributes']['offer_id'] == offer['id']
            and r['attributes']['demand_id'] != demand_id
        )
        offers.append(
            {
                **offer,
                'compatible': is_compatible(world, offer, demand),
                'available_for_need': max(
                    0, offer['attributes']['quantity'] - used_elsewhere
                ),
            }
        )
    allocations = [
        relation
        for relation in active
        if relation['attributes']['demand_id'] == demand_id
    ]
    return {
        'demand': demand,
        'resource': world['nodes'][demand['target_id']],
        'offers': offers,
        'allocations': allocations,
        'minimum': demand['attributes']['quantity'],
        'unit': demand['attributes']['unit'],
        'offered': sum(o['available_for_need'] for o in offers if o['compatible']),
        'committed': sum(
            r['attributes']['quantity']
            for r in allocations
            if r['status'] in {'committed', 'verified'}
        ),
        'verified': sum(
            r['attributes']['quantity']
            for r in allocations
            if r['status'] == 'verified'
        ),
    }


def project_now(world):
    required = required_requirements(world)
    active = active_allocations(world)
    for requirement in required:
        if 'demand_id' not in requirement['rule']:
            continue
        demand = world['relations'][requirement['rule']['demand_id']]
        supports = [r for r in active if r['attributes']['demand_id'] == demand['id']]
        pending = {
            r['status'] for r in supports if r['status'] in {'proposed', 'committed'}
        }
        requirement['progress'] = {
            'verified': sum(
                r['attributes']['quantity']
                for r in supports
                if r['status'] == 'verified'
            ),
            'minimum': demand['attributes']['quantity'],
            'unit': demand['attributes']['unit'],
            'pending_status': 'committed'
            if 'committed' in pending
            else 'proposed'
            if pending
            else None,
        }
    return {
        'satisfied': sum(r['status'] == 'satisfied' for r in required),
        'total': len(required),
        'feasible': is_feasible(world),
        'requirements': required,
    }


NODE_VIEWS = {
    'people': {'person', 'collective'},
    'places': {'place'},
    'resources': {'resource', 'object'},
}


def project_world(world, view):
    if view == 'world':
        return world
    if view == 'now':
        return project_now(world)
    if view == 'ecosystem':
        return ecosystem(world)
    if view == 'network':
        return {
            'nodes': list(world['nodes'].values()),
            'relations': list(world['relations'].values()),
        }
    if view in NODE_VIEWS:
        return [
            node for node in world['nodes'].values() if node['kind'] in NODE_VIEWS[view]
        ]
    if view in {'requirements', 'actions'}:
        return list(world[view].values())
    raise ValueError('unknown_projection')
