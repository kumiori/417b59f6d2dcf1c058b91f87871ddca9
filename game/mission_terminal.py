"""The book-presentation menu over the existing STOP 01 play forms."""
from functools import partial
import sys

from game_gamer_semantics.assistant import suggested_keys
from game_gamer_semantics.projections import connection_declarations

from .i18n import translator
from .declarations import (
    LEGACY_PROFILE_LIMITS, actor_declarations, taxonomy, validate_legacy_profile_value,
)
from .missions import mission_proposals
from .model import PROFILE_FIELDS
from .play import PlayTerminal
from .profile_editor import DETAIL_LABELS, edit_profile, supports_editor
from .recap import render_journey


PROFILE_LABELS = {'offers': 'I can offer', 'needs': 'I am looking for', 'interests': 'My interests or capabilities'}
BOOK_TITLE = 'Non ho mai imparato'
MINT = '\x1b[38;5;157m'
LAVENDER = '\x1b[38;5;183m'
GREY = '\x1b[38;5;246m'
RESET = '\x1b[0m'
# Scenario hints route players to existing condition forms.
MISSION_TAGS = {
    'requirement_003': {'space'},
    'requirement_004': {'coordination', 'communication'},
    'requirement_005': {'space', 'material'},
    'requirement_006': {'creative', 'technical', 'communication'},
}


class MissionTerminal(PlayTerminal):
    def __init__(self, *args, proposer=None, semantic_assistant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.proposer = proposer
        self.semantic_assistant = semantic_assistant
        self.interactive_profile = supports_editor(self.source, self.output)

    def accent(self, text, colour=MINT):
        return f'{colour}{text}{RESET}' if self.interactive_profile else text

    def profile_lines(self, person, world):
        profile = person['metadata'].get('profile', {})
        for field in DETAIL_LABELS:
            if field in profile:
                self.write(f'    {self._(DETAIL_LABELS[field])}: {profile[field]}')
        for declaration in actor_declarations(world, person['id']).values():
            if declaration['status'] != 'shared':
                continue
            direction = declaration['direction'] + 's'
            categories = ', '.join(self._(taxonomy().label(key)) for key in declaration['categories'])
            tags = f' [{categories}]' if categories else ''
            label = self.accent(self._(PROFILE_LABELS[direction]), MINT if direction == 'offers' else LAVENDER)
            self.write(f"    {label}: {declaration['description']}{tags}")

    def support_label(self, relation, nodes):
        source, target = (nodes[relation[key]]['label'] for key in ('source_id', 'target_id'))
        attrs = relation['attributes']
        status = relation['status']
        if relation['kind'] == 'offers' and status == 'reported':
            status = 'offered'
        quantity = f" · {attrs['quantity']} {self._(attrs['unit'])}" if 'quantity' in attrs else ''
        return f'{source} → {self._(target)}{quantity} · {self._(status)}'

    def observe(self, now):
        world = self.game.get_world()
        nodes, relations = world['nodes'], world['relations']
        event = nodes['event_001']
        gathering = event['metadata']
        self.write(self.accent(BOOK_TITLE, LAVENDER))
        date_status = 'verified' if world['requirements']['requirement_004']['status'] == 'satisfied' else 'proposed'
        self.write(self._('Gathering: {place} · {date} ({status})').format(
            place=nodes[gathering['location_id']]['label'], date=gathering['proposed_date'],
            status=self._(date_status)))
        self.write(self.accent(self._('Presentation conditions')))
        for condition in now['requirements']:
            rule = condition['rule']
            relation = relations.get(rule.get('relation_id'))
            label = self._(condition['metadata']['label'])
            if relation and relation['kind'] == 'participates_in':
                label = self._('Hube participation') + f" ({nodes[relation['source_id']]['label']})"
            status = self._('verified' if condition['status'] == 'satisfied' else condition['status'])
            mark = '✓' if condition['status'] == 'satisfied' else '·'
            self.write(f"  {self.accent(f'[{mark}]', MINT if mark == '✓' else GREY)} {label} — {status}")
            if 'demand_id' in rule:
                need = self.game.project_need(rule['demand_id'])
                self.write('    ' + self._('Offered: {offered}/{minimum} · committed: {committed}/{minimum} · verified: {verified}/{minimum}').format(**need))
            elif relation and relation['id'] in condition['satisfied_by']:
                self.write('    ' + self.support_label(relation, nodes))

        for view, label in [('people', 'People'), ('places', 'Places'), ('resources', 'Resources')]:
            self.write(self._(label))
            for node in self.game.project(view):
                self.write('  ' + (node['label'] if view == 'people' else self._(node['label'])))
                if view == 'people':
                    self.profile_lines(node, world)
        for kind, label in [('offers', 'Offers'), ('needs', 'Other needs'), ('satisfies', 'Commitments')]:
            self.write(self._(label))
            visible = [r for r in relations.values() if r['kind'] == kind and r['status'] not in {'withdrawn', 'rejected'}]
            for relation in visible:
                self.write('  ' + self.support_label(relation, nodes))
            if not visible:
                self.write('  ' + self._('none'))
        overview = self.game.project('ecosystem')
        covered = sum(bool(row['offer_declarations']) for row in overview['coverage'].values())
        self.write(self._('Profile categories offered: {covered}/{total} · Potential connections: {pairs}').format(
            covered=covered, total=len(overview['categories']), pairs=len(overview['connections'])))

    def potential_connections(self):
        world = self.game.get_world()
        nodes = world['nodes']
        ecosystem = self.game.project('ecosystem')
        connections = {f"{row['provider_id']}→{row['seeker_id']}": row for row in ecosystem['connections']}
        self.write(self.accent(self._('Potential connections from shared profile categories')))
        self.write(self._('Category overlap suggests a conversation. Offers, commitments and verification use the game actions.'))
        if not connections:
            self.write(self._('No potential connections yet.'))
            return
        ranked = suggested_keys(self.semantic_assistant, 'connections', {
            'connections': {key: {**value, **connection_declarations(ecosystem, value)}
                            for key, value in connections.items()},
        }, connections)

        def label(key):
            pair = connections[key]
            return (f"{nodes[pair['provider_id']]['label']} → {nodes[pair['seeker_id']]['label']}"
                    f" · {', '.join(self._(ecosystem['categories'][tag]) for tag in pair['categories'])}")

        selected = self.form(lambda d: d.choose('Inspect a potential connection',
                                                list(dict.fromkeys([*ranked, *connections])), label))
        if selected is None:
            return
        pair = connections[selected]
        self.write(label(selected))
        for direction, declarations in connection_declarations(ecosystem, pair).items():
            self.write(self._(PROFILE_LABELS[direction + 's']))
            for declaration in declarations:
                self.write('  ' + declaration['description'])
        missions = self.matching_missions(set(pair['categories']))
        for mission in missions:
            self.write(self._('Related mission condition: {condition}').format(
                condition=self._(mission['metadata']['label'])))
        if self.game.project('now')['feasible']:
            return
        if self.form(lambda d: d.yes('See available game actions?', default=False)):
            if self.session is not None or self.choose_identity():
                self.connection_actions(pair, missions)

    def matching_missions(self, categories):
        return [condition for condition in self.game.project('now')['requirements']
                if condition['status'] != 'satisfied'
                and categories.intersection(MISSION_TAGS.get(condition['id'], ()))]

    def connection_actions(self, pair, missions):
        introduction = {'kind': 'introduce', 'source_id': pair['provider_id'], 'target_id': pair['seeker_id']}
        options = []
        def valid(command):
            return not self.game.validate({**command, 'actor': self.actor, 'key': self.key()})

        if valid(introduction):
            options.append((self._('Introduce these players'), partial(self.submit_command, introduction)))
        provider = pair['provider_id']
        name = self.game.get_world()['nodes'][provider]['label']
        for condition in missions:
            demand_id = condition['rule']['demand_id']
            resource = self._(condition['metadata']['label'])
            options.append((resource, partial(self.work_on_condition, demand_id)))
            request = {'kind': 'request', 'recipient_id': provider, 'demand_id': demand_id}
            if valid(request):
                label = self._('Ask {name} about {resource}').format(name=name, resource=resource)
                options.append((label, partial(self.submit_command, request)))
        choice = self.form(lambda d: d.choose('Choose an action', options, lambda option: option[0]))
        if choice and self.form(lambda d: d.yes('Continue with this action?', default=False)):
            choice[1]()

    def work_on_condition(self, demand_id):
        world = self.game.get_world()
        demand = world['relations'][demand_id]
        resource = self._(world['nodes'][demand['target_id']]['label'])
        def advise(context):
            ecosystem = self.game.project('ecosystem')
            return suggested_keys(self.semantic_assistant, 'mission_actions', {
                'actor_id': context.actor_id, 'demand_id': context.demand_id,
                'declarations': ecosystem['declarations'],
                'conditions': context.world['requirements'],
                'candidates': context.candidates,
            }, {move['id'] for move in context.candidates}, limit=3)

        proposer = self.proposer or (advise if self.semantic_assistant else None)
        for move in mission_proposals(self.session, demand_id, proposer):
            if move['kind'] == 'match':
                self.write(self.possibility_label(move))
            else:
                person = world['nodes'][move['source_ids'][0]]
                self.write(self._('You could ask {name} about {resource}.').format(
                    name=person['label'], resource=resource))
                self.profile_lines(person, world)
        self.work_on(demand_id)

    def act(self, now):
        self.write(self._('The provider confirms the commitment. Another player verifies it.'))
        world = self.game.get_world()
        self.profile_lines(world['nodes'][self.actor], world)
        offered = {category for declaration in actor_declarations(world, self.actor).values()
                   if declaration['direction'] == 'offer' and declaration['status'] == 'shared'
                   for category in declaration['categories']}
        for condition in self.matching_missions(offered):
            self.write(self.accent(self._('Your profile may help with {condition}.').format(
                condition=self._(condition['metadata']['label']))))
        options = [
            (self._(condition['metadata']['label']), partial(self.work_on_condition, condition['rule']['demand_id']))
            for condition in now['requirements']
            if condition['status'] != 'satisfied' and 'demand_id' in condition['rule']
        ]
        options.extend((self.need_label(demand), partial(self.work_on_condition, demand['id']))
                       for demand in self.active_needs() if demand['kind'] == 'needs')
        options.extend([
            (self._('Add something to the world'), self.add),
            (self._('Requests waiting for you') + f' ({len(self.session.inbox())})', self.requests),
        ])
        choice = self.form(lambda d: d.choose('What do you want to work on?', options, lambda entry: entry[0]))
        if choice:
            choice[1]()

    def share_profile(self, current):
        self.write(self._('Only the details you confirm will be shared. Previously shared details remain in the event log.'))
        self.write(self._('Press Enter to keep a field as it is. Enter - to clear it.'))

        def profile_text(field, value):
            if value == '-':
                return None
            validate_legacy_profile_value(field, value)
            return value

        def collect(dialogue):
            values = {
                field: dialogue.text(
                    self._(PROFILE_LABELS[field]) + '?', default=current.get(field, ''),
                    parse=partial(profile_text, field), keep_default=True,
                    error=self._('Enter up to {limit} characters.').format(limit=limit),
                )
                for field, limit in LEGACY_PROFILE_LIMITS.items()
            }
            profile = {field: value for field, value in values.items() if value}
            if profile != current and dialogue.yes('Share these profile details with players?', default=False):
                return {'kind': 'share_profile', 'profile': profile}
            return None

        self.collect_and_submit(collect)

    def contributions(self, now):
        world = self.game.get_world()
        person = world['nodes'][self.actor]
        self.write(person['label'])
        self.profile_lines(person, world)
        for relation in world['relations'].values():
            if relation['source_id'] == self.actor and relation['kind'] in {'offers', 'needs', 'satisfies'}:
                self.write('  ' + self.support_label(relation, world['nodes']))
        for action in world['actions'].values():
            if action['submitted_by'] == self.actor and action['kind'] == 'verify':
                commitment = world['relations'][action['target_ids'][0]]
                self.write('  ' + self._('You verified') + ' ' + self.support_label(commitment, world['nodes']))
        if not now['feasible']:
            self.write('  [1] ' + self._('Edit shared profile'))
            self.write(self._('b / 0  Back'))
            if self.ask('>') == '1':
                profile = person['metadata'].get('profile', {})
                if self.interactive_profile:
                    command = edit_profile(actor_declarations(world, self.actor), profile, taxonomy(),
                                           person['label'], self._, self.semantic_assistant)
                    if command:
                        self.submit_command(command)
                else:
                    self.share_profile({field: profile[field] for field in PROFILE_FIELDS if field in profile})

    def run(self):
        if self.interactive_profile:
            self.write(self.accent('HUBE', MINT) + self.accent('  /  ' + BOOK_TITLE.upper(), LAVENDER))
            self.write(self.accent('─' * 52, GREY))
        else:
            self.write('HUBE')
            self.write(BOOK_TITLE.upper())
        self.write(self.accent(self._('A book is looking for a gathering.')))
        self.write(self._('People, places and resources already exist. Some connections are missing.'))
        self.write(self._('Explore the situation. Find what you can contribute. Help make the event happen.'))
        try:
            while True:
                now = self.game.project('now')
                self.write()
                self.write(self.accent(self._('MISSION 01 · Organise the book presentation'), LAVENDER))
                bar = '■' * now['satisfied'] + '□' * (now['total'] - now['satisfied'])
                self.write(self._('PROGRESS') + ' ' + self.accent(f"[{bar}] {now['satisfied']} / {now['total']}"))
                if now['feasible']:
                    self.write(self._('STOP 01 complete. The book presentation can happen.'))
                options = [('1', 'OBSERVE ECOSYSTEM')]
                if not now['feasible']:
                    options.append(('2', 'ACT'))
                options.extend([('3', 'MY CONTRIBUTIONS'), ('4', 'JOURNEY / REPLAY'),
                                ('5', 'POTENTIAL CONNECTIONS'), ('0', 'Save and exit')])
                for key, label in options:
                    self.write(f'[{key}] ' + self._(label))
                if self.hot_seat and self.session:
                    self.write(self._('[s] Switch player'))
                if self.session:
                    self.write(self._('You are {name}.').format(name=self.game.get_world()['nodes'][self.actor]['label']))
                choice = self.ask('>')
                if choice == '0':
                    break
                if choice == '1':
                    self.observe(now)
                elif choice == '4':
                    render_journey(self.game.replay().project_journey(), self.output, self.locale)
                elif choice == '5':
                    self.potential_connections()
                elif choice == 's' and self.hot_seat and self.session:
                    self.choose_identity()
                elif choice == '2' and now['feasible']:
                    continue
                elif choice in {'2', '3'}:
                    if self.session is None and not self.choose_identity():
                        continue
                    if choice == '2':
                        self.act(now)
                    else:
                        self.contributions(now)
                else:
                    self.write(self._('I need one of the listed choices.'))
        except EOFError:
            pass
        return self.game


def run_mission(game, source=None, output=None, locale='en', on_change=None, *, hot_seat=False,
                proposer=None, semantic_assistant=None, sandbox=False, fullscreen=True, invite=None):
    source = sys.stdin if source is None else source
    output = sys.stdout if output is None else output
    if fullscreen and source is sys.stdin and output is sys.stdout:
        from .tui_mission import run_fullscreen, supports_fullscreen
        if supports_fullscreen(source, output):
            return run_fullscreen(game, locale=locale, on_change=on_change, sandbox=sandbox,
                                  hot_seat=hot_seat, proposer=proposer, invite=invite,
                                  semantic_assistant=semantic_assistant)
    if invite:
        raise ValueError('Local invitation redemption needs the interactive terminal.')
    if sandbox:
        output.write(translator(locale)('Disposable simulation') + '\n')
    terminal = MissionTerminal(game, source, output, locale, on_change, hot_seat=hot_seat,
                               proposer=proposer, semantic_assistant=semantic_assistant)
    terminal.interactive_profile = False
    return terminal.run()
