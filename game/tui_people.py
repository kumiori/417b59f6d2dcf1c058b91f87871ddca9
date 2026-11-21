"""Browse Hube's people, shared profiles and their local networks."""

from game_gamer.tui.text import folded, pad

from .declarations import actor_declarations, taxonomy
from .ecosystem_graph import ecosystem_graph
from .profile_editor import COLUMN_LABELS, DETAIL_LABELS
from .tui_graph import render_network
from .tui_screen import RETURN


def profile_sections(actions, person, world):
    translate = actions._
    actor = person['id']
    profile = person['metadata'].get('profile', {})
    records = list(actor_declarations(world, actor).values())
    details = [
        f'{translate(label)} · {profile.get(field) or translate("Unknown")}'
        for field, label in DETAIL_LABELS.items()
    ]
    for direction, label in COLUMN_LABELS.items():
        details.append(translate(label))
        rows = [r for r in records if r['direction'] == direction]
        descriptions = [
            format_declaration(r, translate) for r in rows if r['status'] == 'shared'
        ]
        details.extend(
            descriptions
            or [translate('Nothing currently shared' if rows else 'Unknown')]
        )
    contributions = [
        actions.support_label(r, world['nodes'])
        for r in world['relations'].values()
        if r['source_id'] == actor and r['kind'] in {'offers', 'needs', 'satisfies'}
    ]
    return details, contributions


def format_declaration(record, translate):
    tags = ', '.join(translate(taxonomy().label(key)) for key in record['categories'])
    return record['description'] + (f' · {tags}' if tags else '')


def ask_person(actions, person):
    if not actions.ensure_player() or person['id'] == actions.actor:
        return

    def collect(d):
        demand = d.choose(
            'What would you like to ask about?',
            actions.active_needs(),
            actions.need_label,
        )
        prompt = actions._('Ask {name} about {need}?').format(
            name=person['label'],
            need=actions.need_label(demand),
        )
        if d.yes(prompt, default=False):
            return {
                'kind': 'request',
                'recipient_id': person['id'],
                'demand_id': demand['id'],
            }
        return None

    actions.collect_and_submit(collect)


class PeopleDirectory:
    def __init__(self, actions):
        self.actions = actions
        self.screen = actions.screen
        self._ = self.screen._
        self.query = ''
        self.index = self.region = 0

    def run(self):
        while True:
            world = self.actions.game.get_world()
            people = sorted(
                (
                    node
                    for node in world['nodes'].values()
                    if node['kind'] == 'person'
                    and folded(self.query) in folded(node['label'])
                ),
                key=lambda node: (folded(node['label']), node['id']),
            )
            self.index = min(self.index, max(0, len(people) - 1))
            person = people[self.index] if people else None
            self.paint(world, people, person)
            key = self.screen.key()
            if key in RETURN:
                return
            self.handle(key, world, people, person)

    def can_ask(self, person):
        return (
            person is not None
            and not self.actions.game.project('now')['feasible']
            and (not self.actions.session or person['id'] != self.actions.actor)
        )

    def handle(self, key, world, people, person):
        if key == '/':
            query = self.screen.text('Search people', [])
            if query is not None:
                self.query, self.index = query, 0
        elif key in {'up', 'down'} and people:
            self.index = (self.index + (1 if key == 'down' else -1)) % len(people)
        elif key in {'tab', 'backtab'}:
            self.region = (self.region + (1 if key == 'tab' else -1)) % 3
        elif key == 'enter' and person:
            details, contributions = profile_sections(self.actions, person, world)
            self.screen.read(
                'About me',
                [person['label'], *details, self._('Contributions'), *contributions],
            )
        elif key == 'a' and self.can_ask(person):
            ask_person(self.actions, person)
        elif key == '?':
            self.screen.help(
                [
                    self._('↑↓ Browse people · / Search · Tab Switch region'),
                    self._('Enter Read full profile · a Ask about a mission need'),
                ]
            )

    def paint(self, world, people, person):
        width, height = self.screen.viewport.size()
        footer = '↑↓ Browse · / Search · Tab Switch region · Enter Profile · Esc/b Back · ? Help'
        if self.can_ask(person):
            footer = 'a Ask · ' + footer
        if person is None:
            self.screen.draw(
                'People', [self._('No people match your search.')], footer=footer
            )
            return
        visible = max(1, height - 9)
        start = max(0, self.index - visible + 1)
        directory = [
            ('> ' if n['id'] == person['id'] else '  ') + n['label']
            for n in people[start : start + visible]
        ]
        details, contributions = profile_sections(self.actions, person, world)
        profile = [person['label'], *details, self._('Contributions'), *contributions]
        regions = [self._('Directory'), self._('About me'), self._('Network')]
        head = self._('Search · {query}').format(query=self.query) if self.query else ''
        if width < 79:
            panels = [directory, profile, self.network(person, width - 2, visible)]
            lines = [regions[self.region], head, *panels[self.region]]
        else:
            widths = (width // 4, width // 3, width - width // 4 - width // 3 - 7)
            network = self.network(person, widths[2], visible)
            lines = [
                head,
                *combine_panels(
                    regions, widths, (directory, profile, network), self.region, visible
                ),
            ]
        self.screen.draw('People', lines, footer=footer, fixed=True)

    def network(self, person, width, height):
        graph = ecosystem_graph(self.actions.game)
        lines, _ = render_network(
            graph,
            person['id'],
            width,
            height,
            self._,
            selected=person['id'],
            plain=self.screen.viewport.plain,
        )
        return lines


def combine_panels(titles, widths, panels, focused, height):
    columns = (
        [(('> ' if index == focused else '') + title), *panel]
        for index, (title, panel) in enumerate(zip(titles, panels))
    )
    columns = tuple(columns)
    count = min(height + 1, max(map(len, columns)))
    return [
        '  '.join(
            pad(column[row] if row < len(column) else '', width)
            for width, column in zip(widths, columns)
        )
        for row in range(count)
    ]


def show_people(actions):
    PeopleDirectory(actions).run()
