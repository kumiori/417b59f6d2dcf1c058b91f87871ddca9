"""Project Hube's book, mission, requirements and social relationships."""

from .presentations import BOOK_ID, MISSION_ID, is_candidate
from .projections import project_need


def requirement_state(requirement, allocations, offers):
    if requirement['status'] == 'satisfied':
        return 'Verified'
    states = {record['status'] for record in allocations}
    if states & {'committed', 'verified'}:
        return 'Confirmed'
    if 'proposed' in states:
        return 'Awaiting confirmation'
    if offers:
        return 'Offered'
    return 'Not found'


def requirement_node(world, requirement):
    demand = requirement['rule'].get('demand_id')
    need = project_need(world, demand) if demand else None
    state = requirement_state(
        requirement, need['allocations'] if need else [], need['offers'] if need else []
    )
    return {
        'id': requirement['id'],
        'kind': 'requirement',
        'state': state,
        'label': requirement['metadata']['label'],
        'created_at': world['nodes'][MISSION_ID]['created_at'],
        'demand_id': demand,
        'found': state in {'Verified', 'Confirmed', 'Awaiting confirmation'}
        or bool(need and any(offer['compatible'] for offer in need['offers'])),
    }


def graph_nodes(world):
    requirements = [
        requirement_node(world, r)
        for r in world['requirements'].values()
        if r['required']
    ]
    aliases = {
        world['relations'][node['demand_id']]['target_id']: node['id']
        for node in requirements
        if node['demand_id']
    }
    nodes = [
        dict(node) for node in world['nodes'].values() if node['id'] not in aliases
    ]
    nodes.extend(requirements)
    for node in nodes:
        if node['id'] == BOOK_ID:
            node['label'] = 'Non ho mai imparato'
        elif node['id'] == MISSION_ID:
            node['label'] = 'Book presentation'
    return nodes, aliases


def edge(identifier, source, target, layer, kind, status=''):
    return {
        'id': identifier,
        'source_id': source,
        'target_id': target,
        'layer': layer,
        'kind': kind,
        'status': status,
        'directed': True,
    }


def relation_edge(relation, world, aliases):
    status = relation['status']
    kind = relation['kind']
    target = relation['target_id']
    if kind == 'satisfies':
        target = world['relations'][relation['attributes']['demand_id']]['target_id']
    layer = {
        'proposed': 'invitation',
        'committed': 'documented',
        'verified': 'documented',
    }.get(status, 'declared')
    return edge(
        relation['id'],
        relation['source_id'],
        aliases.get(target, target),
        layer,
        kind,
        status,
    )


def context_edges(world, aliases):
    for node in world['nodes'].values():
        if is_candidate(node):
            yield edge(
                f'candidate:{node["id"]}',
                BOOK_ID,
                node['id'],
                'invitation',
                'Proposed presentation',
                'proposed',
            )
        request = node['metadata'].get('context_request')
        if request:
            demand = world['relations'].get(request['subject'])
            subject = demand['target_id'] if demand else request['subject']
            layer = 'invitation' if request['status'] == 'open' else 'declared'
            yield edge(
                f'ask:{node["id"]}',
                request['inviter'],
                node['id'],
                layer,
                'Something asked',
                request['status'],
            )
            yield edge(
                f'context:{node["id"]}',
                node['id'],
                aliases.get(subject, subject),
                layer,
                'What we need',
                request['status'],
            )


def graph_edges(world, aliases):
    result = [
        edge('book-presentation', BOOK_ID, MISSION_ID, 'documented', 'Presentation')
    ]
    result.extend(
        relation_edge(r, world, aliases)
        for r in world['relations'].values()
        if r['status'] not in {'withdrawn', 'rejected'}
    )
    result.extend(context_edges(world, aliases))
    result.extend(
        edge(
            f'mission:{r["id"]}',
            MISSION_ID,
            r['id'],
            'documented',
            'What we need',
            r['status'],
        )
        for r in world['requirements'].values()
        if r['required'] and 'demand_id' not in r['rule']
    )
    return result


def mission_progress(world):
    requirements = [
        requirement_node(world, r)
        for r in world['requirements'].values()
        if r['required']
    ]
    return {
        'found': sum(r['found'] for r in requirements),
        'confirmed': sum(r['state'] == 'Confirmed' for r in requirements),
        'verified': sum(r['state'] == 'Verified' for r in requirements),
        'total': len(requirements),
    }


def ecosystem_graph(game):
    """Return only derived display records, preserving authoritative IDs on existing objects."""
    world = game.get_world()
    nodes, aliases = graph_nodes(world)
    edges = graph_edges(world, aliases)
    for connection in game.project('ecosystem')['connections']:
        provider, seeker = connection['provider_id'], connection['seeker_id']
        edges.append(
            edge(
                f'overlap:{provider}:{seeker}',
                provider,
                seeker,
                'inferred',
                'Shared profile categories',
            )
        )
    return {'nodes': nodes, 'edges': edges}
