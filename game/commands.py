"""Hube command contracts and mutation planning on detached candidate state."""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from .capacity import (
    ASSET_KINDS,
    attach_asset,
    capacity_attributes,
    is_open_demand,
    possibilities,
)
from .declarations import edit_actor_declarations, prepare_legacy_profile
from .model import (
    Action,
    EVIDENCE_KINDS,
    Evidence,
    NODE_KINDS,
    Node,
    OBSERVATION_KINDS,
    RELATION_KINDS,
    Relation,
    normalize_label,
    relation_valid,
)
from .policies import pending_request

Command = dict[str, Any]
World = dict[str, dict[str, Any]]
REPORTABLE_RELATIONS = frozenset(OBSERVATION_KINDS)

CAPACITY_FIELDS = frozenset(
    {
        'quantity',
        'unit',
        'location_id',
        'available_from',
        'available_until',
        'asset_id',
    }
)


@dataclass
class CommandPlan:
    """A detached candidate world and the action being recorded in it."""

    world: World
    command: Command
    sequence: int
    timestamp: str
    action: dict[str, Any] = field(init=False)

    def __post_init__(self):
        self.action = asdict(
            Action(
                id=self.action_id,
                kind=self.command['kind'],
                submitted_at=self.timestamp,
                submitted_by=self.actor,
                actor_ids=[self.actor],
                occurred_at=self.timestamp,
                payload=deepcopy(self.command),
            )
        )

    @property
    def actor(self) -> str:
        return self.command['actor']

    @property
    def action_id(self) -> str:
        return f'action_{self.sequence:06}'

    def add_node(self, node_kind: str, label: str) -> str:
        if (
            node_kind not in NODE_KINDS
            or not isinstance(label, str)
            or not label.strip()
        ):
            raise ValueError('invalid_node')
        nodes = self.world['nodes']
        if (
            node_kind == 'resource'
            and self.command.get('allow_duplicate_resource') is not True
        ):
            if any(
                n['kind'] == 'resource'
                and normalize_label(n['label']) == normalize_label(label)
                for n in nodes.values()
            ):
                raise ValueError('resource_already_exists')
        base = identifier = f'{node_kind}_{self.sequence:06}'
        suffix = 2
        while identifier in nodes:
            identifier = f'{base}_{suffix}'
            suffix += 1
        nodes[identifier] = asdict(
            Node(
                id=identifier,
                kind=node_kind,
                label=label,
                created_at=self.timestamp,
                created_by=self.actor,
            )
        )
        return identifier

    def add_relation(
        self, source: str, target: str, kind: str, **attributes: Any
    ) -> str:
        nodes = self.world['nodes']
        if kind not in RELATION_KINDS:
            raise ValueError('unknown_relation_kind')
        if not relation_valid(kind, nodes[source]['kind'], nodes[target]['kind']):
            raise ValueError('invalid_relation_signature')
        identifier = f'rel_{self.sequence:06}'
        self.world['relations'][identifier] = asdict(
            Relation(
                id=identifier,
                source_id=source,
                target_id=target,
                kind=kind,
                created_at=self.timestamp,
                created_by=self.actor,
                **attributes,
            )
        )
        return identifier


def join(plan: CommandPlan) -> str:
    world = plan.world
    command = plan.command
    label = command['label']
    if not isinstance(label, str) or not label.strip():
        raise ValueError('invalid_node')
    matches = [
        n
        for n in world['nodes'].values()
        if n['kind'] == 'person' and n['label'] == label
    ]
    if len(matches) > 1 or (matches and matches[0]['metadata'].get('playable')):
        raise ValueError('identity_already_exists')
    nid = matches[0]['id'] if matches else plan.add_node('person', label)
    world['nodes'][nid]['metadata']['playable'] = True
    world['nodes'][nid]['updated_at'] = plan.timestamp
    plan.action['target_ids'] = [nid]
    return 'player.joined'


def share_profile(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    person = world['nodes'][actor]
    current = person['metadata'].get('profile', {})
    profile = prepare_legacy_profile(command['profile'], current)
    if profile != current:
        if profile:
            person['metadata']['profile'] = profile
        else:
            person['metadata'].pop('profile', None)
        person['updated_at'] = plan.timestamp
    plan.action['target_ids'] = [actor]
    return 'profile.shared'


def edit_declarations(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    plan.action['target_ids'] = [
        actor,
        *edit_actor_declarations(world, command, plan.action_id, plan.timestamp),
    ]
    return 'declarations.edited'


def correct(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    old = world['relations'].get(command['subject'])
    if (
        not old
        or old['created_by'] != actor
        or old['status'] != 'reported'
        or old['kind'] not in REPORTABLE_RELATIONS
    ):
        raise ValueError('only_own_reported_observations')
    if (
        command['source_id'] not in world['nodes']
        or command['target_id'] not in world['nodes']
    ):
        raise ValueError('unknown_target')
    if not isinstance(command['reason'], str) or not command['reason'].strip():
        raise ValueError('reason_required')
    old['status'] = 'withdrawn'
    rid = plan.add_relation(
        command['source_id'],
        command['target_id'],
        old['kind'],
        metadata={'supersedes': old['id'], 'reason': command['reason']},
    )
    plan.action['target_ids'] = [old['id'], rid]
    return 'observation.corrected'


def introduce(plan: CommandPlan) -> str:
    world = plan.world
    command = plan.command
    source, target = command['source_id'], command['target_id']
    if source == target or any(
        world['nodes'].get(n, {}).get('kind') != 'person' for n in (source, target)
    ):
        raise ValueError('invalid_introduction')
    rid = plan.add_relation(source, target, 'introduced')
    plan.action['target_ids'] = [rid, source, target]
    return 'introduction.reported'


def observe(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    target = command.get('target_id')
    if target is None:
        target = plan.add_node(command['node_kind'], command['label'])
    if target not in world['nodes']:
        raise ValueError('unknown_target')
    # Observations cannot manufacture capacities or verified requirements.
    default_relation = (
        'knows'
        if world['nodes'][target]['kind'] in {'person', 'collective'}
        else 'suggests'
    )
    relation_kind = command.get('relation_kind', default_relation)
    if relation_kind not in REPORTABLE_RELATIONS:
        raise ValueError('invalid_observation_relation')
    source = command.get('source_id', actor)
    if source not in world['nodes']:
        raise ValueError('unknown_source')
    extra = {}
    if 'note' in command:
        if not isinstance(command['note'], str) or not command['note'].strip():
            raise ValueError('note_required')
        extra['metadata'] = {'note': command['note']}
    plan.add_relation(source, target, relation_kind, **extra)
    plan.action['target_ids'] = [target]
    return 'observation.reported'


def request(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    recipient = world['nodes'].get(command['recipient_id'])
    demand = world['relations'].get(command['demand_id'])
    if not recipient or recipient['kind'] != 'person' or recipient['id'] == actor:
        raise ValueError('invalid_recipient')
    if not demand or not is_open_demand(demand):
        raise ValueError('invalid_demand')
    if pending_request(world, actor, recipient['id'], demand['id']):
        raise ValueError('request_already_pending')
    attributes = deepcopy(demand['attributes'])
    attributes.update(demand_id=demand['id'], action_id=plan.action_id)
    if command.get('via_relation_id'):
        context = world['relations'].get(command['via_relation_id'])
        if (
            not context
            or context['kind'] not in {'knows', 'introduced', 'suggests'}
            or recipient['id'] not in {context['source_id'], context['target_id']}
            or context['status'] in {'withdrawn', 'rejected'}
        ):
            raise ValueError('invalid_request_context')
        attributes['via_relation_id'] = context['id']
    rid = plan.add_relation(
        actor, recipient['id'], 'requested', status='proposed', attributes=attributes
    )
    plan.action.update(
        status='proposed', target_ids=[rid, demand['id'], recipient['id']]
    )
    return 'request.sent'


def respond(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    request = world['relations'].get(command['subject'])
    if not request or request['kind'] != 'requested' or request['status'] != 'proposed':
        raise ValueError('request_not_pending')
    if request['target_id'] != actor:
        raise ValueError('recipient_required')
    response = command['response']
    if response not in {'accept', 'decline', 'modify'}:
        raise ValueError('invalid_response')
    if response != 'modify' and CAPACITY_FIELDS.intersection(command):
        raise ValueError('modify_required')
    if response == 'decline':
        request['status'] = 'rejected'
        world['actions'][request['attributes']['action_id']]['status'] = 'rejected'
    else:
        demand = world['relations'][request['attributes']['demand_id']]
        if not is_open_demand(demand):
            raise ValueError('invalid_demand')
        capacity = {
            **request['attributes'],
            **{k: command[k] for k in CAPACITY_FIELDS if k in command},
        }
        attributes = capacity_attributes(capacity, world)
        attach_asset(world, demand['target_id'], attributes, capacity.get('asset_id'))
        attributes['request_id'] = request['id']
        offer_id = plan.add_relation(
            actor, demand['target_id'], 'offers', attributes=attributes
        )
        request['status'] = 'reported'  # answered, not a verified event commitment
        request['attributes']['offer_id'] = offer_id
        world['actions'][request['attributes']['action_id']]['status'] = 'accepted'
    request['attributes']['response'] = response
    plan.action['target_ids'] = [request['id']]
    return 'request.responded'


def propose(plan: CommandPlan) -> str:
    actor = plan.actor
    command = plan.command
    target = plan.add_node('proposition', command['label'])
    plan.add_relation(actor, target, 'proposes', status='proposed')
    plan.action.update(status='proposed', target_ids=[target])
    return 'proposition.proposed'


def act(plan: CommandPlan) -> str:
    world = plan.world
    command = plan.command
    possibility = next(
        (p for p in possibilities(world) if p['id'] == command['possibility_id']), None
    )
    if possibility is None:
        raise ValueError('stale_possibility')
    offer = world['relations'][possibility['source_ids'][0]]
    demand = world['relations'][possibility['target_ids'][0]]
    attributes = deepcopy(offer['attributes'])
    attributes.update(
        {
            'offer_id': offer['id'],
            'demand_id': demand['id'],
            'quantity': possibility['reason']['parameters']['quantity'],
            'action_id': plan.action_id,
        }
    )
    cid = plan.add_relation(
        offer['source_id'],
        demand['target_id'],
        'satisfies',
        status='proposed',
        attributes=attributes,
    )
    plan.action.update(
        kind='commit', status='proposed', target_ids=[cid, offer['id'], demand['id']]
    )
    return 'connection.proposed'


def report_capacity(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    resource = command.get('resource_id')
    if resource is None:
        resource = plan.add_node('resource', command['resource_label'])
    if resource not in world['nodes'] or world['nodes'][resource]['kind'] != 'resource':
        raise ValueError('invalid_resource')
    capacity = deepcopy(command)
    if command.get('location_label'):
        if command.get('location_id'):
            raise ValueError('choose_location_or_label')
        capacity['location_id'] = plan.add_node('place', command['location_label'])
    attributes = capacity_attributes(capacity, world)
    asset_id = command.get('asset_id')
    if command.get('asset_label'):
        if asset_id is not None:
            raise ValueError('choose_asset_or_label')
        asset_kind = command.get('asset_kind', 'place')
        if asset_kind not in ASSET_KINDS:
            raise ValueError('invalid_asset')
        asset_id = plan.add_node(asset_kind, command['asset_label'])
    attach_asset(world, resource, attributes, asset_id)
    plan.add_relation(
        actor,
        resource,
        'offers' if command['kind'] == 'offer' else 'needs',
        attributes=attributes,
    )
    plan.action['target_ids'] = [resource]
    return 'capacity.reported' if command['kind'] == 'offer' else 'need.reported'


def withdraw_or_reject(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    subject = world['relations'].get(command['subject'])
    if not subject or subject['kind'] not in {
        'offers',
        'needs',
        'satisfies',
        'proposes',
    }:
        raise ValueError('invalid_subject')
    if subject['source_id'] != actor:
        raise ValueError('owner_required')
    if subject['status'] not in {'reported', 'proposed', 'committed', 'verified'}:
        raise ValueError('invalid_transition')
    if command['kind'] == 'reject' and subject['status'] != 'proposed':
        raise ValueError('invalid_transition')
    if not isinstance(command.get('reason'), str) or not command['reason'].strip():
        raise ValueError('reason_required')
    status = 'withdrawn' if command['kind'] == 'withdraw' else 'rejected'
    subject['status'] = status
    subject['metadata']['reason'] = command['reason']
    # Withdrawing an offer also removes all its pending/verified allocations.
    dependents = [
        r
        for r in world['relations'].values()
        if r['attributes'].get('offer_id') == subject['id']
        or r['attributes'].get('demand_id') == subject['id']
    ]
    for related in [subject] + dependents:
        related['status'] = status
        if related['attributes'].get('action_id'):
            world['actions'][related['attributes']['action_id']]['status'] = status
    plan.action.update(status=status, target_ids=[subject['id']])
    return 'commitment.' + status


def commitment(plan: CommandPlan):
    subject = plan.world['relations'].get(plan.command['subject'])
    if subject is None or subject['kind'] != 'satisfies':
        raise ValueError('invalid_subject')
    return subject, plan.world['actions'][subject['attributes']['action_id']]


def confirm(plan: CommandPlan) -> str:
    actor = plan.actor
    subject, original_action = commitment(plan)
    plan.action['target_ids'] = [subject['id']]
    if subject['source_id'] != actor:
        raise ValueError('provider_confirmation_required')
    if subject['status'] != 'proposed':
        raise ValueError('invalid_transition')
    subject['status'] = 'committed'
    original_action['status'] = 'awaiting_verification'
    return 'commitment.confirmed'


def verify(plan: CommandPlan) -> str:
    world = plan.world
    actor = plan.actor
    command = plan.command
    sequence = plan.sequence
    subject, original_action = commitment(plan)
    plan.action['target_ids'] = [subject['id']]
    if subject['status'] != 'committed':
        raise ValueError('commitment_required')
    if subject['source_id'] == actor:
        raise ValueError('independent_verifier_required')
    evidence_kind = command['evidence_kind']
    if evidence_kind not in EVIDENCE_KINDS or evidence_kind == 'self_report':
        raise ValueError('insufficient_evidence')
    if evidence_kind == 'organizer_confirmation' and not any(
        r['kind'] == 'organizes'
        and r['source_id'] == actor
        and r['status'] == 'verified'
        for r in world['relations'].values()
    ):
        raise ValueError('organizer_required')
    reference = command['reference']
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError('evidence_reference_required')
    eid = f'evidence_{sequence:06}'
    world['evidence'][eid] = asdict(
        Evidence(
            id=eid,
            kind=evidence_kind,
            submitted_by=actor,
            submitted_at=plan.timestamp,
            reference=reference,
        )
    )
    subject.update(status='verified', evidence_ids=[eid])
    original_action.update(status='verified', evidence_ids=[eid])
    plan.action.update(status='verified', evidence_ids=[eid])
    return 'commitment.verified'
