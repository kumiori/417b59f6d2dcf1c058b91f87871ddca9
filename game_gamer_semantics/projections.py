"""Declaration counts and category overlaps derived from shared profiles."""
from copy import deepcopy


def declaration_order(record):
    """Order by origin and numeric batch position, with a stable ID tie-break."""
    identifier = record.get('id', '')
    prefix, _, suffix = identifier.rpartition(':')
    position = int(suffix) if prefix.startswith('declaration:') and suffix.isdecimal() else 0
    origin = record.get('provenance', {}).get('created', {}).get('at') or ''
    return origin, prefix, position, identifier


def unmatched_needs(shared, providers):
    unmatched = []
    for record in shared:
        if record['direction'] != 'need':
            continue
        missing = [key for key in record['categories'] if not providers[key] - {record['actor_id']}]
        if not record['categories'] or len(missing) == len(record['categories']):
            unmatched.append({
                'declaration': record,
                'reason': 'no_interpersonal_offer' if missing else 'uncategorized',
            })
    return unmatched


def project_ecosystem(players, declarations, taxonomy):
    players = sorted(set(players))
    player_set = set(players)
    shared = sorted(
        (deepcopy(record) for record in declarations
         if record['actor_id'] in player_set and record['status'] == 'shared'),
        key=declaration_order,
    )
    retired = {key for record in shared for key in record['categories']} - set(taxonomy.keys)
    categories = [*taxonomy.keys, *sorted(retired)]
    offers = {actor: dict.fromkeys(categories, 0) for actor in players}
    needs = {actor: dict.fromkeys(categories, 0) for actor in players}
    for record in shared:
        matrix = offers if record['direction'] == 'offer' else needs
        for key in record['categories']:
            matrix[record['actor_id']][key] += 1

    providers = {key: {actor for actor in players if offers[actor][key]} for key in categories}
    coverage = {
        key: {
            'offering_players': len(providers[key]),
            'seeking_players': sum(bool(needs[actor][key]) for actor in players),
            'offer_declarations': sum(offers[actor][key] for actor in players),
            'need_declarations': sum(needs[actor][key] for actor in players),
        }
        for key in categories
    }
    potential = {actor: dict.fromkeys(players, 0) for actor in players}
    connections = []
    for provider in players:
        for seeker in players:
            if provider == seeker:
                continue
            overlap = [key for key in categories if offers[provider][key] and needs[seeker][key]]
            potential[provider][seeker] = len(overlap)
            if overlap:
                connections.append({
                    'provider_id': provider, 'seeker_id': seeker, 'categories': overlap,
                })

    return {
        'players': players, 'taxonomy_version': taxonomy.version,
        'categories': {key: taxonomy.label(key) for key in categories},
        'offer_matrix': offers, 'need_matrix': needs, 'potential_matrix': potential,
        'coverage': coverage, 'connections': connections, 'unmatched_needs': unmatched_needs(shared, providers),
        'uncategorized': [record for record in shared if not record['categories']],
        'declarations': shared,
    }


def connection_declarations(ecosystem, connection):
    """Return the declarations contributing to a directed overlap."""
    categories = set(connection['categories'])
    return {
        direction: [record for record in ecosystem['declarations']
                    if record['actor_id'] == actor and record['direction'] == direction
                    and categories.intersection(record['categories'])]
        for direction, actor in [('offer', connection['provider_id']), ('need', connection['seeker_id'])]
    }
