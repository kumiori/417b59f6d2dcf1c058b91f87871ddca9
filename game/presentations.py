"""Presentation proposals, scoped contribution rules and independent progress."""

from dataclasses import dataclass
from datetime import date

from .commands import CommandPlan
from .requirements import required_requirements

MISSION_ID = 'event_001'
BOOK_ID = 'object_001'


@dataclass(frozen=True)
class CandidateRequirement:
    id: str
    label: str
    minimum: int


def candidate_requirements(world):
    result = {}
    for requirement in required_requirements(world):
        demand_id = requirement['rule'].get('demand_id')
        demand = world['relations'].get(demand_id, {})
        minimum = demand.get('attributes', {}).get('quantity', 1)
        key = requirement['id']
        result[key] = CandidateRequirement(
            key, requirement['metadata']['label'], minimum
        )
    return result


def is_candidate(node):
    return (
        node['kind'] == 'event' and node['metadata'].get('candidate_for') == MISSION_ID
    )


def candidate_node(world, identifier):
    node = world['nodes'].get(identifier)
    if not node or not is_candidate(node):
        raise ValueError('invalid_presentation')
    return node


def candidate_progress(world, candidate):
    requirements = candidate_requirements(world)
    progress = dict.fromkeys(requirements, 0)
    for support in candidate['metadata']['contributions'].values():
        if support['status'] == 'verified':
            progress[support['requirement_id']] += support['quantity']
    return [(requirement, progress[key]) for key, requirement in requirements.items()]


def candidate_is_feasible(world, candidate):
    progress = candidate_progress(world, candidate)
    return bool(progress) and all(
        quantity >= requirement.minimum for requirement, quantity in progress
    )


def text_value(text, error, *, optional=False):
    if not isinstance(text, str):
        raise ValueError(error)
    if optional and text == '':
        return text
    if not text.strip() or not text.isprintable():
        raise ValueError(error)
    return text.strip()


def propose_presentation(plan: CommandPlan) -> str:
    command = plan.command
    city = text_value(command['city'], 'invalid_presentation_city')
    venue = text_value(
        command.get('venue', ''), 'invalid_presentation_venue', optional=True
    )
    try:
        proposed_date = date.fromisoformat(command['date']).isoformat()
    except (TypeError, ValueError) as error:
        raise ValueError('invalid_presentation_date') from error
    identifier = plan.add_node('event', f'{city} · {proposed_date}')
    plan.world['nodes'][identifier]['metadata'] = {
        'candidate_for': MISSION_ID,
        'book_id': BOOK_ID,
        'city': city,
        'venue': venue,
        'proposed_date': proposed_date,
        'contributions': {},
    }
    plan.action['target_ids'] = [identifier, BOOK_ID, MISSION_ID]
    return 'presentation.proposed'


def offer_to_presentation(plan: CommandPlan) -> str:
    command = plan.command
    candidate = candidate_node(plan.world, command['subject'])
    requirements = candidate_requirements(plan.world)
    key = command['requirement_id']
    if key not in requirements:
        raise ValueError('invalid_presentation_requirement')
    quantity = command.get('quantity', 1)
    if type(quantity) is not int or quantity <= 0:
        raise ValueError('positive_integer_quantity_required')
    detail = text_value(command['detail'], 'detail_required')
    candidate['metadata']['contributions'][plan.action_id] = {
        'id': plan.action_id,
        'actor': plan.actor,
        'requirement_id': key,
        'quantity': quantity,
        'detail': detail,
        'status': 'offered',
    }
    plan.action['target_ids'] = [candidate['id'], key]
    return 'presentation.support_offered'


def candidate_support(plan):
    candidate = candidate_node(plan.world, plan.command['subject'])
    contribution = candidate['metadata']['contributions'].get(
        plan.command['contribution_id']
    )
    if not contribution:
        raise ValueError('invalid_subject')
    return candidate, contribution


def confirm_presentation_offer(plan: CommandPlan) -> str:
    candidate, support = candidate_support(plan)
    if plan.actor != support['actor']:
        raise ValueError('provider_confirmation_required')
    if support['status'] != 'offered':
        raise ValueError('invalid_transition')
    support['status'] = 'committed'
    plan.action['target_ids'] = [candidate['id'], support['id']]
    return 'presentation.support_confirmed'


def verify_presentation_offer(plan: CommandPlan) -> str:
    candidate, support = candidate_support(plan)
    if support['status'] != 'committed':
        raise ValueError('commitment_required')
    if plan.actor == support['actor']:
        raise ValueError('independent_verifier_required')
    reference = text_value(plan.command['reference'], 'evidence_reference_required')
    was_feasible = candidate_is_feasible(plan.world, candidate)
    support.update(
        status='verified',
        verification={
            'actor': plan.actor,
            'reference': reference,
            'action_id': plan.action_id,
        },
    )
    plan.action['target_ids'] = [candidate['id'], support['id']]
    if not was_feasible and candidate_is_feasible(plan.world, candidate):
        return 'presentation.feasible'
    return 'presentation.support_verified'
