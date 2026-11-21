"""Amend owned contributions and place labels without replacing their identities."""

from .capacity import active_allocations, capacity_attributes
from .commands import CommandPlan
from .model import normalize_label

AMENDABLE_FIELDS = frozenset({'quantity', 'available_from', 'available_until'})


def capacity_edit_error(world, actor, relation):
    if not relation or relation['kind'] not in {'offers', 'needs'}:
        return 'invalid_subject'
    if relation['source_id'] != actor:
        return 'owner_required'
    if relation['status'] != 'reported':
        return 'invalid_transition'
    if relation['attributes'].get('request_id') or any(
        relation['id'] in {r['attributes']['offer_id'], r['attributes']['demand_id']}
        for r in active_allocations(world)
    ):
        return 'capacity_has_dependencies'
    if any(
        r['kind'] == 'requested'
        and r['status'] == 'proposed'
        and r['attributes'].get('demand_id') == relation['id']
        for r in world['relations'].values()
    ):
        return 'capacity_has_dependencies'
    return None


def amend_capacity(plan: CommandPlan) -> str:
    relation = plan.world['relations'].get(plan.command['subject'])
    error = capacity_edit_error(plan.world, plan.actor, relation)
    if error:
        raise ValueError(error)
    changes = {
        key: plan.command[key] for key in AMENDABLE_FIELDS if key in plan.command
    }
    if not changes:
        raise ValueError('missing_field')
    attributes = capacity_attributes({**relation['attributes'], **changes}, plan.world)
    if any(relation['attributes'][key] != value for key, value in attributes.items()):
        relation['attributes'].update(attributes)
    plan.action['target_ids'] = [relation['id'], relation['target_id']]
    return 'capacity.amended'


def place_edit_error(world, actor, place):
    if not place or place['kind'] != 'place':
        return 'invalid_place'
    if place['created_by'] != actor:
        return 'owner_required'
    if any(
        place['id']
        in {
            rel['source_id'],
            rel['target_id'],
            rel['attributes'].get('asset_id'),
            rel['attributes'].get('location_id'),
        }
        for rel in world['relations'].values()
        if rel['status'] in {'committed', 'verified'}
    ):
        return 'place_has_dependencies'
    return None


def rename_place(plan: CommandPlan) -> str:
    place = plan.world['nodes'].get(plan.command['subject'])
    error = place_edit_error(plan.world, plan.actor, place)
    if error:
        raise ValueError(error)
    label = plan.command['label']
    if not isinstance(label, str) or not label.strip() or not label.isprintable():
        raise ValueError('invalid_node')
    label = label.strip()
    if any(
        node['id'] != place['id']
        and node['kind'] == 'place'
        and normalize_label(node['label']) == normalize_label(label)
        for node in plan.world['nodes'].values()
    ):
        raise ValueError('place_already_exists')
    if label != place['label']:
        place.update(label=label, updated_at=plan.timestamp)
    plan.action['target_ids'] = [place['id']]
    return 'place.renamed'
