"""Hube's capacity, asset compatibility and allocation policies."""

from datetime import date


ASSET_KINDS = frozenset({'place', 'object'})
DEMAND_KINDS = frozenset({'needs', 'requires'})
ACTIVE_ALLOCATION_STATES = frozenset({'proposed', 'committed', 'verified'})


def is_open_demand(relation):
    return relation['kind'] in DEMAND_KINDS and relation['status'] not in {
        'withdrawn',
        'rejected',
    }


def is_available_offer(relation):
    return relation['kind'] == 'offers' and relation['status'] in {
        'reported',
        'verified',
    }


def active_allocations(world):
    return [
        relation
        for relation in world['relations'].values()
        if relation['kind'] == 'satisfies'
        and relation['status'] in ACTIVE_ALLOCATION_STATES
    ]


def capacity_attributes(command, world):
    quantity = command['quantity']
    if type(quantity) is not int or quantity <= 0:
        raise ValueError('positive_integer_quantity_required')
    if not isinstance(command['unit'], str) or not command['unit'].strip():
        raise ValueError('unit_required')
    location = world['nodes'].get(command['location_id'])
    if not location or location['kind'] != 'place':
        raise ValueError('invalid_location')
    start = date.fromisoformat(command['available_from'])
    end = date.fromisoformat(command['available_until'])
    if start > end:
        raise ValueError('invalid_interval')
    attributes = {
        'quantity': quantity,
        'unit': command['unit'],
        'location_id': location['id'],
        'available_from': start.isoformat(),
        'available_until': end.isoformat(),
    }
    if 'scope' in command:
        scope = command['scope']
        if not isinstance(scope, str) or not scope.strip() or not scope.isprintable():
            raise ValueError('detail_required')
        attributes['scope'] = scope.strip()
    return attributes


def attach_asset(world, resource_id, attributes, asset_id):
    """Validate an explicit asset against its location and resource."""
    if asset_id is None:
        return
    asset = world['nodes'].get(asset_id)
    if (
        not asset
        or asset['kind'] not in ASSET_KINDS
        or asset_id == attributes['location_id']
    ):
        raise ValueError('invalid_asset')

    required_kinds = {
        relation['attributes']['required_asset_kind']
        for relation in world['relations'].values()
        if relation['kind'] == 'requires'
        and relation['target_id'] == resource_id
        and relation['attributes'].get('required_asset_kind')
    }
    if required_kinds and asset['kind'] not in required_kinds:
        raise ValueError('invalid_asset')
    attributes['asset_id'] = asset_id


def capacity_mismatches(world, offer, demand):
    """Explain the same compatibility rules used by the allocation engine."""
    supplied, needed = offer['attributes'], demand['attributes']
    asset_kind = needed.get('required_asset_kind')
    asset = world['nodes'].get(supplied.get('asset_id'), {})
    checks = (
        (offer['target_id'] == demand['target_id'], 'Different resource'),
        (supplied['unit'] == needed['unit'], 'Different unit'),
        (supplied['location_id'] == needed['location_id'], 'Different location'),
        (supplied['available_from'] <= needed['available_from'], 'Availability starts too late'),
        (supplied['available_until'] >= needed['available_until'], 'Availability ends too early'),
        (not asset_kind or asset.get('kind') == asset_kind, 'A specific suitable place or object is needed'),
    )
    return [reason for compatible, reason in checks if not compatible]


def is_compatible(world, offer, demand):
    return not capacity_mismatches(world, offer, demand)


def possibilities(world):
    """Derive proposed allocations from open demand and unreserved capacity."""
    relations = world['relations'].values()
    allocations = active_allocations(world)
    offers = [relation for relation in relations if is_available_offer(relation)]
    result = []
    for demand in filter(is_open_demand, relations):
        allocated = sum(
            r['attributes']['quantity']
            for r in allocations
            if r['attributes']['demand_id'] == demand['id']
        )
        missing = demand['attributes']['quantity'] - allocated
        if missing <= 0:
            continue
        for offer in offers:
            if not is_compatible(world, offer, demand):
                continue
            used = sum(
                r['attributes']['quantity']
                for r in allocations
                if r['attributes']['offer_id'] == offer['id']
            )
            remaining = offer['attributes']['quantity'] - used
            if remaining <= 0:
                continue
            identifier = 'match:' + demand['id'] + ':' + offer['id']
            result.append(
                {
                    'id': identifier,
                    'kind': 'match',
                    'source_ids': [offer['id']],
                    'target_ids': [demand['id']],
                    'reason': {
                        'code': 'need_offer_match',
                        'parameters': {'quantity': min(missing, remaining)},
                    },
                    'confidence': None,
                    'generator': 'deterministic',
                    'created_at': max(offer['created_at'], demand['created_at']),
                    'expires_at': None,
                    'suggested_commands': [
                        {'kind': 'act', 'possibility_id': identifier}
                    ],
                }
            )
    return result
