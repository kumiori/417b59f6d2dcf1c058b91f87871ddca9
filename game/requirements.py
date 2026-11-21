"""Evaluate STOP 01 requirements from verified support."""

from .capacity import active_allocations


def required_requirements(world):
    return [
        requirement
        for requirement in world['requirements'].values()
        if requirement['required']
    ]


def is_feasible(world):
    required = required_requirements(world)
    return bool(required) and all(
        requirement['status'] == 'satisfied' for requirement in required
    )


def evaluate_requirements(world, timestamp):
    """Update requirement status and supporting relation IDs on candidate state."""
    verified = [
        relation
        for relation in active_allocations(world)
        if relation['status'] == 'verified'
    ]
    for requirement in world['requirements'].values():
        rule = requirement['rule']
        if requirement['kind'] == 'relation_exists':
            relation = world['relations'].get(rule['relation_id'])
            supports = (
                [relation['id']]
                if relation and relation['status'] == 'verified'
                else []
            )
            satisfied, partial = bool(supports), False
        else:
            demand = world['relations'][rule['demand_id']]
            supporting = [
                relation
                for relation in verified
                if relation['attributes']['demand_id'] == demand['id']
            ]
            supports = [relation['id'] for relation in supporting]
            quantity = sum(
                relation['attributes']['quantity'] for relation in supporting
            )
            satisfied = quantity >= demand['attributes']['quantity']
            partial = quantity > 0
        status = (
            'satisfied'
            if satisfied
            else 'partially_satisfied'
            if partial
            else 'unsatisfied'
        )
        requirement.update(
            status=status,
            satisfied_by=supports,
            satisfied_at=(requirement['satisfied_at'] or timestamp)
            if satisfied
            else None,
        )
