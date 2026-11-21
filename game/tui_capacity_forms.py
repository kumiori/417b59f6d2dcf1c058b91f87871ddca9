"""Resource-specific forms for the known STOP 01 mission demands."""


def venue(actions, d, command, demand):
    command.update(
        actions.asset(d, {'location_id': command['location_id']}, required=True)
    )
    availability(d, command, demand)


def accommodation(actions, d, command, demand):
    command['quantity'] = d.quantity('How many people can you host?')
    availability(d, command, demand)


def availability(d, command, demand):
    start = d.date('Available from (YYYY-MM-DD)?', default=demand['available_from'])
    end = d.date(
        'Available until (YYYY-MM-DD)?',
        default=max(start, demand['available_until']),
        minimum=start,
    )
    command.update(available_from=start, available_until=end)


def date_availability(actions, d, command, demand):
    selected = d.date(
        'Date you can make (YYYY-MM-DD)', default=demand['available_from']
    )
    command.update(available_from=selected, available_until=selected)


def documentation(actions, d, command, demand):
    command['scope'] = d.text('How could you document the event?')
    availability(d, command, demand)


FORMS = {
    'bed': accommodation,
    'venue': venue,
    'confirmation': date_availability,
    'commitment': documentation,
}


def mission_offer(actions, d, need, builder):
    resource, demand = need['resource']['label'], need['demand']['attributes']
    command = {
        'kind': 'offer',
        'resource_id': need['resource']['id'],
        'quantity': 1,
        'unit': demand['unit'],
        'location_id': demand['location_id'],
    }
    builder(actions, d, command, demand)
    city = actions.game.get_world()['nodes'][demand['location_id']]['label']
    summary = actions._('Share {resource} · {city} · {start} → {end}?').format(
        resource=actions._(resource),
        city=city,
        start=command['available_from'],
        end=command['available_until'],
    )
    if 'scope' in command:
        summary += ' ' + command['scope']
    return command if d.yes(summary, default=False) else None
