"""Create and answer gameplay requests on the same local save."""

from secrets import token_urlsafe

from .context_requests import (
    invitation_for,
    request_context,
    request_nodes,
    token_digest,
)

AUDIENCES = (
    ('existing', 'Ask an existing player'),
    ('invite', 'Invite someone new'),
    ('open', 'Leave an open request'),
)
REPLIES = (
    ('I can help', 'help'),
    ('I know someone who might', 'refer'),
    ('I need more information', 'question'),
    ('I cannot help', 'decline'),
)


def create_request(actions, subject):
    game, screen = actions.game, actions.screen
    context = request_context(game.get_world(), subject)
    choices = [(screen._(label), value) for value, label in AUDIENCES]
    audience, _ = screen.choose('Request confirmation', choices, [screen._(context)])
    if audience is None:
        return
    token = token_urlsafe(24) if audience == 'invite' else None
    command = actions.form(lambda d: request_form(d, actions, subject, audience, token))
    if command:
        result = actions.submit_command(command)
        if result['ok'] and token:
            screen.read(
                'Local invitation',
                [
                    screen._('Use this token with the same local save.'),
                    token,
                    'game --db <shared-save> play --invite ' + token,
                ],
            )


def request_form(d, actions, subject, audience, token):
    command = {'kind': 'create_context_request', 'subject': subject}
    if audience == 'existing':
        people = [
            node
            for node in actions.game.project('people')
            if node['id'] != actions.actor
        ]
        person = d.choose(
            'Who would you like to ask?', people, lambda node: node['label']
        )
        command['recipient_id'] = person['id']
    if token:
        command['invite_digest'] = token_digest(token)
    command['question'] = d.text('What would you like them to help with?')
    summary = actions._('Share request · {question}?').format(
        question=command['question']
    )
    return command if d.yes(summary, default=False) else None


def redeem(actions, token, explore):
    invitation = invitation_for(actions.game.get_world(), token)
    if invitation is None:
        actions.screen.read(
            'Local invitation', [actions._('This invitation is unavailable.')]
        )
    else:
        show_request(actions, invitation, explore, token=token)


def available_requests(actions, explore):
    world, screen = actions.game.get_world(), actions.screen
    entries = []
    for node in request_nodes(world):
        request = node['metadata']['context_request']
        relevant = actions.actor in {
            request['inviter'],
            request.get('recipient_id'),
            request.get('responder'),
        }
        public = not request.get('recipient_id') and not request.get('invite_digest')
        if relevant or public:
            entries.append((node['label'], node))
    if not entries:
        screen.read('Requests', [screen._('No contextual requests for this player.')])
        return
    selected, _ = screen.choose('Requests', entries)
    if selected:
        show_request(actions, selected, explore)


def show_request(actions, node, explore, *, token=None):
    world, screen = actions.game.get_world(), actions.screen
    request = node['metadata']['context_request']
    context = request_context(world, request['subject'])
    inviter = world['nodes'][request['inviter']]['label']
    lines = [
        screen._('A book is looking for a gathering.'),
        screen._('From {name} · {context}').format(
            name=inviter, context=screen._(context)
        ),
        request['question'],
    ]
    if request['status'] == 'answered':
        reply = next(label for label, key in REPLIES if key == request['response'])
        name = world['nodes'][request['responder']]['label']
        screen.read(
            'Request',
            [
                *lines,
                screen._('Response from {name}').format(name=name),
                screen._(reply),
            ],
        )
        return
    if request.get('invite_digest') and not token:
        screen.read(
            'Request', [*lines, screen._('Waiting for the invited player to respond.')]
        )
        return
    if not token and actions.actor == request['inviter']:
        screen.read('Request', [*lines, screen._('Waiting for a response.')])
        return
    answer_request(actions, node['id'], lines, explore, token)


def answer_request(actions, subject, lines, explore, token):
    screen = actions.screen
    entries = [(screen._(label), key) for label, key in REPLIES]
    entries.append((screen._('Explore the world'), 'explore'))
    while True:
        choice, _ = screen.choose(
            'Local invitation' if token else 'Request', entries, lines
        )
        if choice is None:
            return
        if choice == 'explore':
            explore()
        elif actions.ensure_player():
            command = {
                'kind': 'respond_context_request',
                'subject': subject,
                'response': choice,
            }
            if token:
                command['token'] = token
            if actions.submit_command(command)['ok']:
                return
