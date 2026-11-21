"""Inspect and amend a player's work through authorised game commands."""

from .contribution_commands import capacity_edit_error, place_edit_error
from .declarations import actor_declarations, taxonomy
from .profile_editor import draft_on_screen

EDIT_PROFILE = ('profile', '')
REASONS = {
    'capacity_has_dependencies': 'A request or allocation depends on this contribution.',
    'place_has_dependencies': 'A confirmed or verified contribution depends on this place.',
    'invalid_transition': 'This contribution is no longer awaiting confirmation.',
    'owner_required': 'Only the author can make this change.',
}
CONTRIBUTION_KINDS = {'offers', 'needs', 'satisfies', 'proposes', 'requested'}
WITHDRAWABLE = CONTRIBUTION_KINDS - {'requested'}


def show_contributions(actions):
    screen, game, actor = actions.screen, actions.game, actions.actor
    index = 0
    while True:
        world = game.get_world()
        person = world['nodes'][actor]
        actions.profile_lines(person, world)
        lines = [person['label'], *actions.take_lines()]
        ended = game.project('now')['feasible']
        entries = [] if ended else [(screen._('Edit shared profile'), EDIT_PROFILE)]
        entries.extend(own_entries(actions, world, actor))
        choice, index = screen.choose('My contributions', entries, lines, index=index)
        if choice is None:
            return
        screen.notice = ''
        if choice == EDIT_PROFILE:
            command = draft_on_screen(
                screen,
                actor_declarations(world, actor),
                person['metadata'].get('profile', {}),
                taxonomy(),
                person['label'],
                actions.semantic_assistant,
            )
            if command:
                actions.submit_command(command)
        else:
            inspect_contribution(actions, world, choice, ended)


def own_entries(actions, world, actor):
    nodes = world['nodes']
    entries = [
        (actions.support_label(relation, nodes), ('relation', relation['id']))
        for relation in world['relations'].values()
        if relation['kind'] in CONTRIBUTION_KINDS
        and actor
        in (
            relation['source_id'],
            relation['target_id'] if relation['kind'] == 'requested' else None,
        )
    ]
    entries.extend(
        (node['label'], ('place', node['id']))
        for node in nodes.values()
        if node['kind'] == 'place' and node['created_by'] == actor
    )
    return entries


def inspect_contribution(actions, world, choice, ended):
    screen, actor = actions.screen, actions.actor
    kind, key = choice
    if kind == 'place':
        place = world['nodes'][key]
        lines = [place['label'], screen._('Place')]
        reason = place_edit_error(world, actor, place)
        entries = [(screen._('Correct the place name'), 'rename')] if not reason else []
    else:
        relation = world['relations'][key]
        lines = relation_details(actions, world, relation)
        reason = capacity_edit_error(world, actor, relation)
        entries = [(screen._('Edit contribution'), 'amend')] if not reason else []
        if can_withdraw(relation, actor):
            entries.append((screen._('Withdraw contribution'), 'withdraw'))
    if ended:
        screen.read('Contribution', [*lines, screen._('The mission is complete.')])
        return
    if reason in REASONS:
        lines.append(screen._(REASONS[reason]))
    if not entries:
        screen.read('Contribution', lines)
        return
    selected, _ = screen.choose('Contribution', entries, lines)
    if selected:
        actions.collect_and_submit(
            lambda d: contribution_edit(d, screen._, selected, world, key)
        )


def can_withdraw(relation, actor):
    return (
        relation['kind'] in WITHDRAWABLE
        and relation['source_id'] == actor
        and relation['status'] in {'reported', 'proposed', 'committed', 'verified'}
    )


def relation_details(actions, world, relation):
    lines = [actions.support_label(relation, world['nodes'])]
    attrs = relation['attributes']
    if 'scope' in attrs:
        lines.append(attrs['scope'])
    if 'available_from' in attrs:
        lines.append(f'{attrs["available_from"]} → {attrs["available_until"]}')
    key = relation['id']
    for other in world['relations'].values():
        if key in {
            other['attributes'].get(field)
            for field in ('offer_id', 'demand_id', 'request_id')
        }:
            lines.append(actions.support_label(other, world['nodes']))
    request = world['relations'].get(attrs.get('request_id'))
    if request:
        lines.append(actions.support_label(request, world['nodes']))
    return lines


def contribution_edit(d, translate, selected, world, key):
    if selected == 'rename':
        label = d.text('Correct place name', default=world['nodes'][key]['label'])
        command = {'kind': 'rename_place', 'subject': key, 'label': label}
        summary = translate('Correct place name to {name}?').format(name=label)
    elif selected == 'withdraw':
        reason = d.text('Reason?')
        command = {'kind': 'withdraw', 'subject': key, 'reason': reason}
        summary = translate('Withdraw this contribution?')
    else:
        attrs = world['relations'][key]['attributes']
        quantity = d.text(
            'Quantity?', default=str(attrs['quantity']), parse=parse_quantity
        )
        start = d.date('Available from (YYYY-MM-DD)?', default=attrs['available_from'])
        end = d.date(
            'Available until (YYYY-MM-DD)?',
            default=max(start, attrs['available_until']),
            minimum=start,
        )
        command = {
            'kind': 'amend_capacity',
            'subject': key,
            'quantity': quantity,
            'available_from': start,
            'available_until': end,
        }
        summary = translate('Save {quantity} {unit} · {start} → {end}?').format(
            quantity=quantity,
            unit=translate(attrs['unit']),
            start=start,
            end=end,
        )
    return command if d.yes(summary, default=False) else None


def parse_quantity(raw):
    quantity = int(raw)
    if quantity <= 0:
        raise ValueError('positive_integer_quantity_required')
    return quantity
