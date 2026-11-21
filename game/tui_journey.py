"""Narrate shared changes alongside the seeded STOP 01 causal recap."""

from io import StringIO

from .recap import render_journey

EVENT_LABELS = {
    'presentation.proposed': '{name} proposed {subject}',
    'presentation.support_offered': '{name} offered a contribution to {subject}',
    'presentation.support_confirmed': '{name} confirmed a contribution to {subject}',
    'presentation.support_verified': '{name} verified a contribution to {subject}',
    'presentation.feasible': '{name} verified the final contribution to {subject}',
    'context_request.opened': '{name} asked for help · {subject}',
    'context_request.answered': '{name} replied · {subject}',
    'place.renamed': '{name} corrected the place name · {subject}',
    'capacity.amended': '{name} edited a contribution · {subject}',
}


def world_changes(world, log, translate):
    changes = []
    for event in log:
        template = EVENT_LABELS.get(event['kind'])
        if not template:
            continue
        actor = world['nodes'][event['actor_id']]['label']
        action = world['actions'][event['action_id']]
        recorded = {
            change['entity_id']: change['after']
            for change in event['mutations']
            if change['entity_type'] == 'node'
        }
        subject = next(
            (
                recorded.get(key, world['nodes'][key])['label']
                for key in action['target_ids']
                if key in world['nodes']
            ),
            '',
        )
        changes.append(
            translate(template).format(name=actor, subject=translate(subject))
        )
    return changes


def show_journey(game, screen, locale):
    output = StringIO()
    render_journey(game.project_journey(), output, locale)
    lines = world_changes(game.get_world(), game.project('log'), screen._)
    if lines:
        lines.extend(('', screen._('STOP 01 recap')))
    screen.read('Journey', lines + output.getvalue().splitlines())
