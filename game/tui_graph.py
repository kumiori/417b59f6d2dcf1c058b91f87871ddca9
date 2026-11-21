"""Explore the Hube projection with the shared Game-Gamer graph renderer."""

import math

from game_gamer.tui.network import draw_graph, focus_graph

from .ecosystem_graph import BOOK_ID, ecosystem_graph
from .presentations import is_candidate
from .tui_screen import RETURN

LAYERS = (
    (None, 'All relationships'),
    ('documented', 'Established'),
    ('declared', 'Declared'),
    ('invitation', 'Proposed'),
    ('inferred', 'Inferred'),
)
TYPES = (
    (None, 'All objects'),
    ('person', 'People'),
    ('place', 'Places'),
    ('requirement', 'What we need'),
    ('object', 'Objects'),
)
GRAPH_FOOTER = '↑↓ Select · Enter Inspect · c Centre · +/- Zoom · l Layer · f Filter · t Text · Esc/b Back · ? Help'


def stable_positions(graph):
    nodes = sorted(
        graph['nodes'], key=lambda node: (node.get('created_at', ''), node['id'])
    )
    return {node['id']: index for index, node in enumerate(nodes)}


def render_network(
    graph,
    centre,
    width,
    height,
    translate,
    *,
    selected=None,
    zoom=1.0,
    whole=False,
    positions=None,
    plain=False,
):
    if width < 15 or height < 5:
        return [translate('Enlarge the terminal to see the graph.')], []
    visual = focus_graph(
        graph,
        centre,
        scope='whole' if whole else 'neighbourhood',
        limit=16,
        labeler=lambda node: translate(node['label']),
    )
    for node in visual['nodes']:
        if node['id'] == BOOK_ID:
            node.update(symbol='◆', ascii_symbol='*')
        if is_candidate(node):
            node.update(symbol='○', ascii_symbol='o')
        if node['kind'] == 'requirement':
            symbol = {'Not found': '◌', 'Verified': '●'}.get(node['state'], '○')
            node.update(symbol=symbol, ascii_symbol='o')
        if positions is not None and node['id'] != centre:
            angle = positions[node['id']] * 2.3999632297
            node['position'] = [7 * math.cos(angle), 3 * math.sin(angle), 0]
    return draw_graph(
        visual,
        width,
        height,
        selected=selected,
        zoom=zoom,
        plain=plain,
        background='hidden',
        labeler=lambda node: translate(node['label']),
    )


class GraphView:
    def __init__(self, actions, text_view):
        self.actions = actions
        self.screen = actions.screen
        self._ = self.screen._
        self.text_view = text_view
        self.graph = ecosystem_graph(actions.game)
        self.positions = stable_positions(self.graph)
        self.centre = self.selected = BOOK_ID
        self.zoom = 1.0
        self.layer = self.type = self.page = 0

    def filtered(self):
        kind, _ = TYPES[self.type]
        layer, _ = LAYERS[self.layer]
        nodes = [
            n
            for n in self.graph['nodes']
            if not kind or n['kind'] == kind or n['id'] == self.centre
        ]
        ids = {n['id'] for n in nodes}
        edges = [
            e
            for e in self.graph['edges']
            if e['source_id'] in ids
            and e['target_id'] in ids
            and (not layer or e['layer'] == layer)
        ]
        return {'nodes': nodes, 'edges': edges}

    def paint(self):
        graph = self.filtered()
        width, height = self.screen.viewport.size()
        graph, choices = self.page_graph(graph)
        node = next(n for n in graph['nodes'] if n['id'] == self.selected)
        lines = [
            self._(node['label'])
            + (' · ' + self._(node['state']) if 'state' in node else ''),
            self._(LAYERS[self.layer][1])
            + ' / '
            + self._(TYPES[self.type][1])
            + f' · {self.page + 1}',
        ]
        drawn, styles = render_network(
            graph,
            self.centre,
            width - 2,
            height - 9,
            self._,
            selected=self.selected,
            zoom=self.zoom,
            whole=True,
            positions=self.positions,
            plain=self.screen.viewport.plain,
        )
        styles = [(row + len(lines), *rest) for row, *rest in styles]
        self.screen.draw(
            'Explore the world',
            lines + drawn,
            fixed=True,
            styles=styles,
            footer=GRAPH_FOOTER,
        )
        return choices

    def page_graph(self, graph):
        others = sorted(
            (n for n in graph['nodes'] if n['id'] != self.centre),
            key=lambda node: self.positions[node['id']],
        )
        if self.page * 16 >= len(others):
            self.page = 0
        centre = next(n for n in graph['nodes'] if n['id'] == self.centre)
        nodes = [centre, *others[self.page * 16 : (self.page + 1) * 16]]
        identifiers = [n['id'] for n in nodes]
        if self.selected not in identifiers:
            self.selected = self.centre
        return {'nodes': nodes, 'edges': graph['edges']}, identifiers

    def inspect(self):
        node = next(node for node in self.graph['nodes'] if node['id'] == self.selected)
        lines = [self._(node['label']), self._(node.get('state', node['kind']))]
        if node.get('demand_id'):
            need = self.actions.game.project_need(node['demand_id'])
            lines.extend(self.actions.describe_need(need))
        else:
            labels = {n['id']: self._(n['label']) for n in self.graph['nodes']}
            for edge in self.graph['edges']:
                if self.selected in {edge['source_id'], edge['target_id']}:
                    source = labels.get(edge['source_id'], edge['source_id'])
                    target = labels.get(edge['target_id'], edge['target_id'])
                    lines.append(
                        f'{source} → {target} · {self._(edge["kind"])} · {self._(edge["status"])}'
                    )
        self.screen.read('Inspect', lines)

    def run(self):
        operations = {
            'enter': self.inspect,
            't': self.text_view,
            'c': self.recentre,
            '+': lambda: self.change_zoom(0.2),
            '-': lambda: self.change_zoom(-0.2),
            'l': self.next_layer,
            'f': self.next_type,
            'right': self.next_page,
            'left': self.previous_page,
            '?': self.help,
        }
        while True:
            choices = self.paint()
            key = self.screen.key()
            if key in RETURN:
                return
            if key in operations:
                operations[key]()
            elif key in {'up', 'down'}:
                step = 1 if key == 'down' else -1
                self.selected = choices[
                    (choices.index(self.selected) + step) % len(choices)
                ]

    def help(self):
        self.screen.help(
            [
                self._(GRAPH_FOOTER),
                self._('←→ Pages · ◆ Book · ◌ Not found · ○ Proposed · ● Established'),
            ]
        )

    def recentre(self):
        self.centre = self.selected
        self.page, self.zoom = 0, 1.0

    def change_zoom(self, step):
        self.zoom = max(0.6, min(2.0, self.zoom + step))

    def next_layer(self):
        self.layer = (self.layer + 1) % len(LAYERS)

    def next_type(self):
        self.type = (self.type + 1) % len(TYPES)
        self.page = 0

    def next_page(self):
        self.page += 1

    def previous_page(self):
        self.page = max(0, self.page - 1)
