"""Semantic terminal replay. Display time exists only in this client module.

The simulation completes deterministically before presentation starts. Quitting or
pausing the presentation cannot change its canonical world or log.
"""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
import time

from . import load_fixture
from .i18n import translator

BASE_DELAYS = {'initial': .5, 'player_action': 2.5, 'mutation': .5,
               'relation_created': .5, 'possibility': 1.5, 'threshold': 2.0,
               'ending': 3.0}


@dataclass(frozen=True)
class PresentationEvent:
    kind: str
    text: str
    sequence: int
    simulation_timestamp: str
    actor: str | None = None


def simulate(name='hube-stop-01', locale='en'):
    """Return the canonical result and a disposable ordered presentation stream."""
    if name != 'hube-stop-01':
        raise ValueError('unknown_fixture')
    scenario = json.loads((Path(__file__).parent / 'scenarios/hube_stop_01.json').read_text())
    game = load_fixture(scenario['fixture'])
    _ = translator(locale)
    events = []

    def emit(kind, text, entry, actor=None):
        events.append(PresentationEvent(kind, text, entry['sequence'], entry['occurred_at'], actor))

    initial = game.project('log')[0]
    checklist = '\n'.join(f"{_(r['metadata']['label']):<24} {'✓' if r['status'] == 'satisfied' else '?'}"
                          for r in game.project('requirements'))
    emit('initial', 'HUBE / STOP 01\n' + '─' * 40 + '\n' +
         _('The event does not exist yet.') + '\n' +
         _('Marco is here. Andres coordinates. Editor has books.') + '\n' + checklist + '\n2 / 6', initial)
    known_possibilities = set()
    for command in scenario['commands']:
        result = game.submit(command)
        if not result['ok']:
            raise ValueError(result['errors'])
        entry = game.project('log')[-1]
        world = game.get_world()
        nodes, relations = world['nodes'], world['relations']
        actor = nodes[command['actor']]['label']
        kind = command['kind']
        created_relations = [m['after'] for m in entry['mutations'] if m['entity_type'] == 'relation' and m['before'] is None]
        if kind == 'observe':
            r = created_relations[0]
            statement = _('I know {name}.') if r['kind'] == 'knows' else _('I found {name}.')
            statement = statement.format(name=nodes[r['target_id']]['label'])
        elif kind in {'offer', 'need'}:
            r = created_relations[0]
            template = _('I can offer {quantity} {unit}: {resource}.') if kind == 'offer' else _('I need {quantity} {unit}: {resource}.')
            statement = template.format(quantity=r['attributes']['quantity'], unit=_(r['attributes']['unit']), resource=nodes[r['target_id']]['label'])
            if r['attributes'].get('asset_id'):
                statement += ' ' + nodes[r['attributes']['asset_id']]['label'] + '.'
        elif kind == 'act':
            r = created_relations[0]
            statement = _('Connect {provider}’s offer to {resource}.').format(provider=nodes[r['source_id']]['label'], resource=nodes[r['target_id']]['label'])
        elif kind == 'confirm':
            statement = _('I confirm this commitment.')
        elif kind == 'verify':
            statement = _('I verify this commitment.') + '\n' + command['reference']
        else:
            statement = kind
        emit('player_action', statement, entry, actor)
        for mutation in entry['mutations']:
            old, record = mutation['before'], mutation['after']
            entity = mutation['entity_type']
            if entity == 'node' and old is None:
                emit('mutation', _('{name} entered the world.').format(name=record['label']), entry)
            elif entity == 'relation':
                source, target = nodes[record['source_id']]['label'], nodes[record['target_id']]['label']
                if old is None:
                    text = f"{source} ──{_(record['kind'])}──▶ {target}"
                    if record['kind'] == 'satisfies':
                        text += '\n' + _('Proposed connection — waiting for the provider.')
                    elif record['kind'] in {'offers', 'needs'}:
                        a = record['attributes']
                        text += f"\n{a['quantity']} {_(a['unit'])} · {nodes[a['location_id']]['label']} · {a['available_from']} → {a['available_until']}"
                    emit('relation_created', text, entry)
                elif old['status'] != record['status']:
                    emit('mutation', f"{source} → {target}: {_(old['status'])} → {_(record['status'])}", entry)
            elif entity == 'requirement' and old and old['status'] != 'satisfied' and record['status'] == 'satisfied':
                count = sum(r['status'] == 'satisfied' for r in world['requirements'].values())
                emit('threshold', _('{requirement} is now secured.').format(requirement=_(record['metadata']['label'])) + f'\n{count} / 6', entry)
        possibilities = game.derive_possibilities()
        for p in possibilities:
            if p['id'] not in known_possibilities:
                offer, demand = relations[p['source_ids'][0]], relations[p['target_ids'][0]]
                emit('possibility', _('{owner} needs {resource}.\n{provider} can provide it.\nA connection is possible; nobody is committed yet.').format(
                    owner=nodes[demand['source_id']]['label'], resource=nodes[demand['target_id']]['label'], provider=nodes[offer['source_id']]['label']), entry)
        known_possibilities = {p['id'] for p in possibilities}
        if entry['kind'] == 'event.feasible':
            emit('ending', _('THE GAME IS OVER.') + '\nHUBE / STOP 01\n' + _('THE THING CAN HAPPEN.'), entry)
    return game, events


class ReplayDriver:
    """Renderer with injectable clock/input for deterministic, zero-wait tests."""
    def __init__(self, *, output=None, mode='instant', speed=1.0, read_key=None,
                 clock=time.monotonic, locale='en', status=None):
        if mode not in {'instant', 'paced', 'step'}:
            raise ValueError('invalid replay mode')
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError('speed must be finite and positive')
        self.output = output if output is not None else sys.stdout
        self.mode, self.speed, self.clock = mode, speed, clock
        self.read_key = read_key or self._sleep
        self.paused = mode == 'step'
        self.status = status
        self._last_status = None
        self._ = translator(locale)

    @staticmethod
    def _sleep(timeout):
        time.sleep(timeout)
        return None

    def _status(self, clear=False):
        if self.status is not None:
            text = '' if clear else self._('[ replay ×{speed:.1f}{paused} | SPACE pause | +/- speed | ENTER next | q quit ]').format(
                speed=self.speed, paused=self._(' | paused') if self.paused else '')
            if text != self._last_status:
                self.status.write('\r\033[K' + text)
                self.status.flush()
                self._last_status = text

    def _wait(self, duration):
        remaining = duration
        while remaining > 1e-8 or self.paused:
            self._status()
            start = self.clock()
            timeout = .05 if self.paused else min(.05, remaining / self.speed)
            key = self.read_key(timeout)
            if not self.paused:
                remaining -= max(0, self.clock() - start) * self.speed
            if key in {'q', '\x03', '\x04'}:
                return False
            if key == ' ':
                self.paused = not self.paused
            elif key in {'+', '\x1b[C'}:
                self.speed = min(64, self.speed * 2)
            elif key in {'-', '\x1b[D'}:
                self.speed = max(.125, self.speed / 2)
            elif key in {'\r', '\n'} and self.paused:
                return True
        return True

    def play(self, events):
        if self.mode == 'step' and self.read_key == self._sleep:
            raise ValueError('step mode requires interactive input')
        headings = {'mutation': 'WORLD MUTATION', 'relation_created': 'GRAPH CHANGE',
                    'possibility': 'NEW POSSIBILITY', 'threshold': 'THRESHOLD CROSSED'}
        try:
            for event in events:
                self._status(clear=True)
                heading = event.actor.upper() if event.actor else self._(headings[event.kind]) if event.kind in headings else ''
                if heading:
                    self.output.write(heading + '\n')
                self.output.write(event.text + '\n\n')
                self.output.flush()
                if self.mode != 'instant' and not (self.mode == 'step' and event.kind == 'ending') and not self._wait(BASE_DELAYS[event.kind]):
                    return False
            return True
        finally:
            self._status(clear=True)


def add_replay_arguments(parser):
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--instant', action='store_const', dest='mode', const='instant')
    modes.add_argument('--paced', action='store_const', dest='mode', const='paced')
    modes.add_argument('--step', action='store_const', dest='mode', const='step')
    parser.set_defaults(mode='instant')
    parser.add_argument('--speed', type=positive_speed, default=1.0)
    recap = parser.add_mutually_exclusive_group()
    recap.add_argument('--recap', action='store_true', dest='recap', help='Print the causal recap after completion')
    recap.add_argument('--no-recap', action='store_false', dest='recap')
    parser.set_defaults(recap=None)


def positive_speed(value):
    import argparse
    try:
        speed = float(value)
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError
        return speed
    except ValueError:
        raise argparse.ArgumentTypeError('speed must be finite and positive') from None


def play_simulation(name='hube-stop-01', *, mode='instant', speed=1.0, locale='en', recap=None):
    from .replay_input import Keyboard
    # Check interactive requirements before preparing or presenting anything.
    with Keyboard(enabled=mode != 'instant') as keyboard:
        if mode == 'step' and not keyboard.interactive:
            raise ValueError('--step requires a terminal; use --instant for redirected input')
        game, events = simulate(name, locale)
        driver = ReplayDriver(mode=mode, speed=speed, locale=locale,
                              read_key=keyboard.read if keyboard.interactive else None,
                              status=sys.stderr if keyboard.interactive and sys.stderr.isatty() else None)
        completed = driver.play(events)
    if completed:
        from .recap import render_journey, offer_recap
        if recap is True:
            render_journey(game.project_journey('event_001'), locale=locale)
        elif recap is None and sys.stdin.isatty():
            offer_recap(game, locale=locale)
    return game
