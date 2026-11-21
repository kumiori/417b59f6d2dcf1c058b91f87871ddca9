"""Propose and inspect isolated presentations of the book."""

from .presentations import candidate_progress, is_candidate
from .tui_requests import create_request


def proposal_form(d, translate):
    city = d.text('Proposed city')
    date = d.date('Proposed date (YYYY-MM-DD)', default='')
    venue = d.text('Proposed venue (optional)', default='', parse=str)
    text = translate('Share presentation proposal · {city} · {date} · {venue}?').format(
        city=city,
        date=date,
        venue=venue or translate('Venue not found'),
    )
    if d.yes(text, default=False):
        return {
            'kind': 'propose_presentation',
            'city': city,
            'date': date,
            'venue': venue,
        }
    return None


def propose(actions):
    actions.collect_and_submit(lambda d: proposal_form(d, actions._))


def show_presentations(actions):
    screen = actions.screen
    while True:
        world = actions.game.get_world()
        entries = [(screen._('Propose a presentation'), '')]
        entries.extend(
            (node['label'], node['id'])
            for node in world['nodes'].values()
            if is_candidate(node)
        )
        choice, _ = screen.choose(
            'Presentation proposals',
            entries,
            [
                screen._(
                    'Each presentation has its own location, date and contributions.'
                ),
            ],
        )
        if choice is None:
            return
        if choice == '':
            propose(actions)
        else:
            show_presentation(actions, choice)


def show_presentation(actions, identifier):
    screen, game = actions.screen, actions.game
    while True:
        world = game.get_world()
        candidate = world['nodes'][identifier]
        progress = candidate_progress(world, candidate)
        metadata = candidate['metadata']
        lines = [
            f'{metadata["city"]} · {metadata["proposed_date"]}',
            metadata['venue'] or screen._('Venue not found'),
            screen._(
                'Candidate complete'
                if all(q >= r.minimum for r, q in progress)
                else 'Proposed presentation'
            ),
        ]
        lines.extend(
            f'{screen._(requirement.label)} · {screen._("Verified")} {quantity}/{requirement.minimum}'
            for requirement, quantity in progress
        )
        entries = [
            (
                screen._('Offer a contribution'),
                lambda: offer(actions, candidate, progress),
            ),
            (
                screen._('Ask about this presentation'),
                lambda: create_request(actions, identifier),
            ),
        ]
        contributions = sorted(
            metadata['contributions'].values(), key=lambda record: record['id']
        )
        entries.extend(
            (
                support_label(screen, world, row),
                lambda row=row: inspect_support(actions, candidate, row),
            )
            for row in contributions
        )
        choice, _ = screen.choose('Presentation', entries, lines)
        if choice is None:
            return
        choice()


def offer(actions, candidate, progress):
    def collect(d):
        require = d.choose(
            'What can you bring into the world?',
            [r for r, _ in progress],
            lambda requirement: actions._(requirement.label),
        )
        quantity = (
            d.quantity('How many people can you host?') if require.minimum > 1 else 1
        )
        detail = d.text('Describe your contribution')
        title = actions._('Share contribution for {presentation}?').format(
            presentation=candidate['label']
        )
        if d.yes(title, default=False):
            return {
                'kind': 'offer_to_presentation',
                'subject': candidate['id'],
                'requirement_id': require.id,
                'quantity': quantity,
                'detail': detail,
            }
        return None

    actions.collect_and_submit(collect)


def support_label(screen, world, support):
    name = world['nodes'][support['actor']]['label']
    return name + ' · ' + screen._(support['status']) + ' · ' + support['detail']


def inspect_support(actions, candidate, support):
    screen = actions.screen
    lines = [candidate['label'], support['detail'], screen._(support['status'])]
    payload = {'subject': candidate['id'], 'contribution_id': support['id']}
    if support['status'] == 'offered' and support['actor'] == actions.actor:
        if actions.form(lambda d: d.yes('Confirm your contribution?', default=False)):
            actions.submit_command({'kind': 'confirm_presentation_offer', **payload})
    elif support['status'] == 'committed' and support['actor'] != actions.actor:

        def verify(d):
            reference = d.text('Evidence reference or note?')
            if d.yes('Verify this contribution?', default=False):
                return {
                    'kind': 'verify_presentation_offer',
                    'reference': reference,
                    **payload,
                }
            return None

        actions.collect_and_submit(verify)
    else:
        evidence = support.get('verification')
        if evidence:
            lines.append(evidence['reference'])
        screen.read('Contribution', lines)
