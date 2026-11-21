"""Route the interactive STOP 01 terminal without keeping a scrollback transcript."""

from game_gamer.tui.viewport import run_curses as run_viewport
from game_gamer.tui.viewport import supported

from .ecosystem_graph import ecosystem_graph, mission_progress
from .tui_actions import MissionActions
from .tui_journey import show_journey
from .tui_screen import MissionScreen
from .tui_words import screen_translator
from .tui_graph import GraphView

MISSION_TITLE = 'STOP 01 · Organise the book presentation'


def supports_fullscreen(source, output):
    # curses.wrapper uses the process's keyboard and terminal streams.
    import sys

    return source is sys.stdin and output is sys.stdout and supported(source, output)


class Mission:
    def __init__(
        self,
        game,
        viewport,
        locale,
        on_change,
        *,
        sandbox=False,
        invite=None,
        **options,
    ):
        self.game = game
        self.locale = locale
        self.sandbox = sandbox
        self.invite = invite
        self._ = screen_translator(locale)
        self.screen = MissionScreen(viewport, self._, self.context)
        self.actions = MissionActions(game, self.screen, locale, on_change, **options)

    def context(self):
        label = self._('Choose a player to act')
        if self.actions.session:
            label = self.game.get_world()['nodes'][self.actions.actor]['label']
        mode = ' · ' + self._('Disposable simulation') if self.sandbox else ''
        return self._(MISSION_TITLE) + ' · ' + label + mode

    def explore(self):
        GraphView(self.actions, self.text_ecosystem).run()

    def text_ecosystem(self):
        graph = ecosystem_graph(self.game)
        labels = {node['id']: self._(node['label']) for node in graph['nodes']}
        lines = [self._('Presentation conditions')]
        lines.extend(
            f'{labels[node["id"]]} · {self._(node["state"])}'
            for node in graph['nodes']
            if node['kind'] == 'requirement'
        )
        lines.extend(
            f'{labels[e["source_id"]]} → {labels[e["target_id"]]} · {self._(e["kind"])}'
            for e in graph['edges']
            if e['source_id'] in labels and e['target_id'] in labels
        )
        self.screen.read('Explore the world', lines)

    def act(self):
        from .tui_presentations import show_presentations
        from .tui_requests import available_requests

        if not self.actions.ensure_player():
            return
        choices = [
            ('Work on STOP 01', lambda: self.actions.act(self.game.project('now'))),
            ('Presentation proposals', lambda: show_presentations(self.actions)),
            (
                'Contextual requests',
                lambda: available_requests(self.actions, self.explore),
            ),
        ]
        selected, _ = self.screen.choose(
            'Act', [(self._(label), action) for label, action in choices]
        )
        if selected:
            selected()

    def contributions(self):
        from .tui_contributions import show_contributions

        if self.actions.ensure_player():
            show_contributions(self.actions)

    def journey(self):
        show_journey(self.game, self.screen, self.locale)

    def possibilities(self):
        ecosystem = self.game.project('ecosystem')
        if not ecosystem['connections']:
            self.empty_possibilities(ecosystem)
            return
        self.actions.potential_connections()
        lines = self.actions.take_lines()
        if lines:
            self.screen.read('Possibilities', lines)

    def empty_possibilities(self, ecosystem):
        counts = list(ecosystem['coverage'].values())
        offered = sum(row['offer_declarations'] for row in counts)
        sought = sum(row['need_declarations'] for row in counts)
        message = (
            'Add a categorised offer and need to look for overlaps.'
            if not offered or not sought
            else 'No shared categories connect different people yet.'
        )
        self.screen.read(
            'Possibilities',
            [
                self._(message),
                self._(
                    'Categorised offers · {offered}   Categorised needs · {sought}'
                ).format(
                    offered=offered,
                    sought=sought,
                ),
            ],
        )

    def people(self):
        from .tui_people import show_people

        show_people(self.actions)

    def run(self):
        routes = [
            ('Explore the world', self.explore),
            ('Act', self.act),
            ('People', self.people),
            ('My contributions', self.contributions),
            ('Possibilities', self.possibilities),
            ('Journey', self.journey),
        ]
        index = 0
        while True:
            self.actions.take_lines()
            now = self.game.project('now')
            options = [
                (self._(label), route)
                for label, route in routes
                if label != 'Act' or not now['feasible']
            ]
            options.append(
                (
                    self._('Save and exit' if not self.sandbox else 'End simulation'),
                    None,
                )
            )
            counts = mission_progress(self.game.get_world())
            progress = self._(
                'Found · {found}/{total}   Confirmed · {confirmed}/{total}   Verified · {verified}/{total}'
            ).format(**counts)
            lines = ['Non ho mai imparato', progress]
            if now['feasible']:
                lines.append(
                    self._('STOP 01 complete. The book presentation can happen.')
                )
            shortcuts = (
                [('s', self._('s Switch player'))]
                if self.actions.hot_seat and self.actions.session
                else []
            )
            chosen, index = self.screen.choose(
                'Mission', options, lines, extra=shortcuts, index=index, reset=True
            )
            self.screen.notice = ''
            if chosen is None:
                return self.game
            if chosen == 's':
                self.actions.choose_identity()
            else:
                chosen()
            index = min(index, len(options) - 2)


def run_fullscreen(game, *, locale, on_change, sandbox=False, **options):
    def run(viewport, plain):
        try:
            mission = Mission(
                game, viewport, locale, on_change, sandbox=sandbox, **options
            )
            if mission.invite:
                from .tui_requests import redeem

                redeem(mission.actions, mission.invite, mission.explore)
            return mission.run()
        except EOFError:
            return game

    return run_viewport(run)
