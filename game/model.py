"""Canonical schema 0.1 records; no presentation dependencies."""
from dataclasses import dataclass, field
from typing import Any
from ._shared import Mutation

NODE_KINDS = {'person', 'collective', 'place', 'event', 'object', 'resource', 'proposition'}
RELATION_KINDS = {'knows', 'introduced', 'suggests', 'collaborates_with', 'offers',
                  'needs', 'requires', 'has_available', 'satisfies', 'participates_in',
                  'organizes', 'hosts', 'supports', 'located_in', 'available_at',
                  'moving_to', 'owns', 'holds', 'created', 'translated', 'transported',
                  'requested', 'proposes', 'supports_proposition', 'opposes_proposition', 'depends_on'}
EVIDENCE_KINDS = {'self_report', 'player_confirmation', 'organizer_confirmation', 'artifact'}
PROFILE_FIELDS = ('offers', 'needs', 'interests')
TABLES = ('nodes', 'relations', 'actions', 'evidence', 'requirements')
ENTITY_TABLE = dict(zip(('node', 'relation', 'action', 'evidence', 'requirement'), TABLES))

@dataclass(kw_only=True)
class Node:
    id: str
    kind: str
    label: str
    created_at: str
    created_by: str
    status: str = 'provisional'
    schema_version: str = '0.1'
    updated_at: str | None = None
    metadata: dict = field(default_factory=dict)

@dataclass(kw_only=True)
class Relation:
    id: str
    source_id: str
    target_id: str
    kind: str
    created_at: str
    created_by: str
    status: str = 'reported'
    schema_version: str = '0.1'
    valid_from: str | None = None
    valid_until: str | None = None
    evidence_ids: list = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

@dataclass(kw_only=True)
class Action:
    id: str
    kind: str
    submitted_at: str
    submitted_by: str
    actor_ids: list = field(default_factory=list)
    target_ids: list = field(default_factory=list)
    status: str = 'accepted'
    occurred_at: str | None = None
    payload: dict = field(default_factory=dict)
    evidence_ids: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    schema_version: str = '0.1'


@dataclass(kw_only=True)
class Evidence:
    id: str
    kind: str
    submitted_by: str
    submitted_at: str
    reference: str | None = None
    content_ref: str | None = None
    metadata: dict = field(default_factory=dict)
    schema_version: str = '0.1'

@dataclass(kw_only=True)
class Requirement:
    id: str
    owner_id: str
    kind: str
    rule: dict
    created_at: str
    created_by: str
    required: bool = True
    status: str = 'unsatisfied'
    satisfied_at: str | None = None
    satisfied_by: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    schema_version: str = '0.1'

# Lightweight domain/range constraints, shared by validation and dialogue choices.
ACTOR_KINDS = {'person', 'collective'}
RELATION_SIGNATURES = {
    'knows': (ACTOR_KINDS, ACTOR_KINDS),
    'introduced': (ACTOR_KINDS, ACTOR_KINDS),
    'collaborates_with': (ACTOR_KINDS, ACTOR_KINDS),
    'located_in': (NODE_KINDS, {'place'}),
    'offers': (ACTOR_KINDS, {'resource'}),
    'needs': (ACTOR_KINDS | {'event'}, {'resource'}),
    'requires': ({'event'}, {'resource'}),
    'satisfies': (ACTOR_KINDS, {'resource'}),
    'requested': (ACTOR_KINDS, ACTOR_KINDS),
    'participates_in': (ACTOR_KINDS, {'event'}),
    'organizes': (ACTOR_KINDS, {'event'}),
    'hosts': ({'place'} | ACTOR_KINDS, {'event'}),
    'holds': (ACTOR_KINDS, {'object'}),
    'owns': (ACTOR_KINDS, {'object', 'place'}),
    'proposes': (ACTOR_KINDS, {'proposition'}),
    'suggests': (NODE_KINDS, NODE_KINDS),
}
OBSERVATION_KINDS = ('knows', 'suggests', 'collaborates_with', 'located_in')


def relation_valid(kind, source_kind, target_kind):
    domain, range_ = RELATION_SIGNATURES.get(kind, (NODE_KINDS, NODE_KINDS))
    return kind in RELATION_KINDS and source_kind in domain and target_kind in range_


def normalize_label(label):
    return ' '.join(label.casefold().split())
