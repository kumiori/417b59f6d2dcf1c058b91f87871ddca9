"""Player-facing words for canonical identifiers used by the full-screen client."""

from .i18n import translator

WORDS = {
    'offers': 'Contribution offered',
    'needs': 'What we need',
    'requires': 'What we need',
    'requested': 'Something asked',
    'satisfies': 'Contribution',
    'proposes': 'Proposal',
    'committed': 'Confirmed',
    'verified': 'Verified',
    'proposed': 'Proposed',
    'offered': 'Offered',
    'reported': 'Shared',
    'withdrawn': 'Withdrawn',
    'rejected': 'Declined',
    'self_report': 'Self-report',
    'organizer_confirmation': 'Organiser confirmation',
    'player_confirmation': 'Player confirmation',
    'owner_required': 'Only the author can make this change.',
    'capacity_has_dependencies': 'A request or allocation depends on this contribution.',
    'place_has_dependencies': 'A confirmed or verified contribution depends on this place.',
    'place_already_exists': 'A place with that name already exists.',
    'invalid_invitation': 'This invitation is unavailable.',
    'recipient_required': 'This request is waiting for someone else.',
    'independent_verifier_required': 'Another player must verify this contribution.',
    'provider_confirmation_required': 'The person offering this contribution must confirm it.',
}


def screen_translator(locale):
    translate = translator(locale)
    return lambda key: translate(WORDS.get(key, key))
