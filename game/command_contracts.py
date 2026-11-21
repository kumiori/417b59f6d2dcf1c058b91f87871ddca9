"""Accepted command payload fields and their mutation handlers."""

from collections.abc import Callable
from dataclasses import dataclass

from . import commands
from .commands import Command, CommandPlan
from .contribution_commands import AMENDABLE_FIELDS, amend_capacity, rename_place
from .context_requests import create_context_request, respond_context_request
from .presentations import (
    confirm_presentation_offer,
    offer_to_presentation,
    propose_presentation,
    verify_presentation_offer,
)


@dataclass(frozen=True)
class CommandSpec:
    handler: Callable[[CommandPlan], str]
    fields: frozenset[str]


CAPACITY_REPORT_FIELDS = commands.CAPACITY_FIELDS | {
    'resource_id',
    'resource_label',
    'allow_duplicate_resource',
    'asset_label',
    'asset_kind',
    'location_label',
    'scope',
}

COMMANDS = {
    'propose_presentation': CommandSpec(
        propose_presentation, frozenset({'date', 'city', 'venue'})
    ),
    'offer_to_presentation': CommandSpec(
        offer_to_presentation,
        frozenset({'subject', 'requirement_id', 'quantity', 'detail'}),
    ),
    'confirm_presentation_offer': CommandSpec(
        confirm_presentation_offer, frozenset({'subject', 'contribution_id'})
    ),
    'verify_presentation_offer': CommandSpec(
        verify_presentation_offer,
        frozenset({'subject', 'contribution_id', 'reference'}),
    ),
    'create_context_request': CommandSpec(
        create_context_request,
        frozenset({'subject', 'question', 'recipient_id', 'invite_digest'}),
    ),
    'respond_context_request': CommandSpec(
        respond_context_request, frozenset({'subject', 'response', 'token'})
    ),
    'amend_capacity': CommandSpec(amend_capacity, AMENDABLE_FIELDS | {'subject'}),
    'rename_place': CommandSpec(rename_place, frozenset({'subject', 'label'})),
    'join': CommandSpec(commands.join, frozenset({'label'})),
    'share_profile': CommandSpec(commands.share_profile, frozenset({'profile'})),
    'edit_declarations': CommandSpec(
        commands.edit_declarations, frozenset({'changes', 'details'})
    ),
    'correct': CommandSpec(
        commands.correct, frozenset({'subject', 'source_id', 'target_id', 'reason'})
    ),
    'introduce': CommandSpec(commands.introduce, frozenset({'source_id', 'target_id'})),
    'observe': CommandSpec(
        commands.observe,
        frozenset(
            {
                'node_kind',
                'label',
                'target_id',
                'relation_kind',
                'source_id',
                'allow_duplicate_resource',
                'note',
            }
        ),
    ),
    'request': CommandSpec(
        commands.request, frozenset({'recipient_id', 'demand_id', 'via_relation_id'})
    ),
    'respond': CommandSpec(
        commands.respond, commands.CAPACITY_FIELDS | {'subject', 'response'}
    ),
    'propose': CommandSpec(commands.propose, frozenset({'label'})),
    'act': CommandSpec(commands.act, frozenset({'possibility_id'})),
    'offer': CommandSpec(commands.report_capacity, CAPACITY_REPORT_FIELDS),
    'need': CommandSpec(commands.report_capacity, CAPACITY_REPORT_FIELDS),
    'withdraw': CommandSpec(
        commands.withdraw_or_reject, frozenset({'subject', 'reason'})
    ),
    'reject': CommandSpec(
        commands.withdraw_or_reject, frozenset({'subject', 'reason'})
    ),
    'confirm': CommandSpec(commands.confirm, frozenset({'subject'})),
    'verify': CommandSpec(
        commands.verify, frozenset({'subject', 'evidence_kind', 'reference'})
    ),
}
ENVELOPE_FIELDS = frozenset({'key', 'actor', 'kind'})


def command_spec(command: Command) -> CommandSpec:
    """Check the command envelope and identify the allowed payload and handler."""
    if not isinstance(command, dict):
        raise ValueError('invalid_command')
    if not isinstance(command.get('key'), str) or not command['key'].strip():
        raise ValueError('key_required')
    spec = COMMANDS.get(command.get('kind'))
    if spec is None:
        raise ValueError('unknown_command')
    if command.keys() - ENVELOPE_FIELDS - spec.fields:
        raise ValueError('unsupported_field')
    return spec
