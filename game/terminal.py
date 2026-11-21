"""Plain stdin/stdout adapter. Game rules and canonical writes live in Game."""
import argparse
import json
from pathlib import Path
import sys
from . import Game, load_fixture
from .i18n import translator

MENU = ('Observe something', 'Offer something', 'Report a need', 'Propose something',
        'Act on a possibility', 'See what is possible', 'See world', 'See timeline',
        'Switch player', 'Confirm a commitment', 'Verify a commitment',
        'Withdraw', 'Reject a proposal')
UNITS = ('bed', 'venue', 'confirmation', 'commitment', 'hour')

class Terminal:
    def __init__(self, game, source, output, locale, on_change=None):
        self.game, self.source, self.output = game, source, output
        self._ = translator(locale)
        self.locale = locale
        self.actor = 'person_001'
        self.on_change = on_change

    def write(self, text=''):
        self.output.write(str(text) + '\n')

    def ask(self, prompt):
        self.write(self._(prompt))
        line = self.source.readline()
        if not line:
            raise EOFError
        return line.rstrip('\r\n')

    def choose(self, prompt, options, label=lambda x: x):
        self.write(self._(prompt))
        for i, item in enumerate(options, 1):
            self.write(f'  {i}  {label(item)}')
        self.write('  0  ' + self._('Cancel'))
        answer = self.ask('>')
        if answer == '0':
            raise InterruptedError
        try:
            index = int(answer)
            if index < 1:
                raise ValueError
            return options[index-1]
        except (ValueError, IndexError):
            raise ValueError('invalid_choice') from None

    def status(self):
        now = self.game.project('now')
        self.write('HUBE / STOP 01')
        for r in now['requirements']:
            mark = '✓' if r['status'] == 'satisfied' else ' '
            detail = self._(r['status'])
            progress = r.get('progress')
            if progress:
                detail += f" ({progress['verified']}/{progress['minimum']} {self._(progress['unit'])})"
                if progress['pending_status']:
                    detail += ' — ' + self._(progress['pending_status']) + ' / ' + self._('unverified')
            self.write(f"[{mark}] {self._(r['metadata']['label'])} — {detail}")
        self.write(self._('{satisfied} / {total} conditions satisfied.').format(**now))
        if now['feasible']:
            self.write('=' * 32)
            self.write(self._('THE GAME IS OVER.'))
            self.write('HUBE / STOP 01')
            self.write(self._('CAN HAPPEN.'))
            self.write('=' * 32)

    def possibilities(self):
        options = self.game.derive_possibilities()
        if not options:
            self.write(self._('No possibilities yet.'))
        return options

    def possibility_label(self, p):
        world = self.game.get_world()
        offer, demand = (world['relations'][p[k][0]] for k in ('source_ids', 'target_ids'))
        return self._('{provider} may supply {quantity} {unit} of {resource} for {owner}.').format(
            provider=world['nodes'][offer['source_id']]['label'],
            quantity=p['reason']['parameters']['quantity'], unit=self._(offer['attributes']['unit']),
            resource=world['nodes'][offer['target_id']]['label'], owner=world['nodes'][demand['source_id']]['label'])

    def commitment_label(self, relation):
        world = self.game.get_world()
        return f"{world['nodes'][relation['source_id']]['label']} → {world['nodes'][relation['target_id']]['label']} ({self._(relation['status'])}) [{relation['id']}]"

    def command(self, choice):
        command = {'key': f"command-{len(self.game.project('log'))+1:06}", 'actor': self.actor}
        if choice == 1:
            nk = self.choose('What did you observe?', ['person', 'place', 'resource', 'relationship'], self._)
            command.update(kind='observe')
            if nk == 'relationship':
                target = self.choose('Choose a target.', list(self.game.get_world()['nodes'].values()), lambda n: n['label'])
                command['target_id'] = target['id']
                command['relation_kind'] = self.choose('Relationship?', ['knows', 'suggests', 'collaborates_with', 'located_in'], self._)
            else:
                command.update(node_kind=nk, label=self.ask('Name?'), relation_kind='knows' if nk == 'person' else 'suggests')
        elif choice in {2, 3}:
            resources = [n for n in self.game.project('resources') if n['kind'] == 'resource']
            resource = self.choose('Resource?', resources + [None], lambda n: n['label'] if n else self._('New resource'))
            command.update(kind='offer' if choice == 2 else 'need', resource_id=resource['id'] if resource else None)
            if resource is None:
                command['resource_label'] = self.ask('Resource name?')
            asset = self.choose('Specific place or object?', [None] + self.game.project('places') +
                                [n for n in self.game.project('resources') if n['kind'] == 'object'],
                                lambda n: n['label'] if n else self._('None'))
            if asset:
                command['asset_id'] = asset['id']
            command['quantity'] = int(self.ask('Quantity?'))
            command['unit'] = self.choose('Unit?', list(UNITS) + ['other'], self._)
            if command['unit'] == 'other':
                command['unit'] = self.ask('Unit name?')
            command['location_id'] = self.choose('Where?', self.game.project('places'), lambda n: n['label'])['id']
            command['available_from'] = self.ask('Available from (YYYY-MM-DD)?')
            command['available_until'] = self.ask('Available until (YYYY-MM-DD)?')
        elif choice == 4:
            command.update(kind='propose', label=self.ask('What do you propose?'))
        elif choice == 5:
            p = self.choose('Choose a possibility.', self.possibilities(), self.possibility_label)
            command.update(kind='act', possibility_id=p['id'])
        elif choice == 6:
            for p in self.possibilities():
                self.write(self.possibility_label(p))
            return
        elif choice == 7:
            self.write(json.dumps(self.game.project('network'), ensure_ascii=False, indent=2))
            return
        elif choice == 8:
            render_timeline(self.game.project('timeline'), self.output, self._)
            return
        elif choice == 9:
            self.actor = self.choose('Choose a player.', [n for n in self.game.project('people') if n['metadata'].get('playable')], lambda n: n['label'])['id']
            return
        elif choice in {10, 11, 12, 13}:
            relations = list(self.game.get_world()['relations'].values())
            if choice in {10, 11}:
                status = 'proposed' if choice == 10 else 'committed'
                relations = [r for r in relations if r['kind'] == 'satisfies' and r['status'] == status]
            else:
                relations = [r for r in relations if r['source_id'] == self.actor and r['kind'] in {'offers', 'needs', 'satisfies', 'proposes'} and r['status'] in {'reported', 'proposed', 'committed', 'verified'}]
            subject = self.choose('Choose a subject.', relations, self.commitment_label)
            command.update(kind={10:'confirm', 11:'verify', 12:'withdraw', 13:'reject'}[choice], subject=subject['id'])
            if choice == 11:
                command['evidence_kind'] = self.choose('Evidence?', ['organizer_confirmation', 'player_confirmation', 'artifact', 'self_report'], self._)
                command['reference'] = self.ask('Evidence reference or note?')
            elif choice in {12, 13}:
                command['reason'] = self.ask('Reason?')
        else:
            raise ValueError('invalid_choice')
        self.submit_command(command)

    def submit_command(self, command):
        result = self.game.submit(command)
        if result['ok']:
            if self.on_change:
                self.on_change(self.game)
            self.write(self._('World changed.'))
        else:
            self.write(self._('Command rejected.') + ' ' + ', '.join(self._(e) for e in result['errors']))

    def run(self):
        self.write(self._('Development hot-seat client. Use game play for a fixed identity.'))
        self.status()
        while not self.game.project('now')['feasible']:
            self.write(self.game.get_world()['nodes'][self.actor]['label'] + ' >')
            for i, item in enumerate(MENU, 1):
                self.write(f'  {i}  {self._(item)}')
            self.write('  0  ' + self._('Save and exit'))
            try:
                choice = int(self.ask('>'))
                if choice == 0:
                    break
                self.command(choice)
                self.status()
            except EOFError:
                break
            except InterruptedError:
                continue
            except ValueError as error:
                self.write(self._('Invalid input.') + ' ' + self._(str(error)))
        if self.game.project('now')['feasible']:
            from .recap import offer_recap
            offer_recap(self.game, self.source, self.output, self.locale)
        return self.game


def render_timeline(entries, output, translate):
    for entry in entries:
        output.write(f"{entry['sequence']:03}  {entry['occurred_at']}  {translate(entry['kind'])}  [{entry['actor_id']}]\n")
        for mutation in entry['mutations']:
            before, after = mutation['before'], mutation['after']
            status = '' if before is None else f" {before.get('status', '')} → {after.get('status', '')}"
            output.write(f"     {mutation['entity_type']} {mutation['entity_id']}{status}\n")


def run_session(game, source=None, output=None, locale='en', on_change=None):
    return Terminal(game, source or sys.stdin, output or sys.stdout, locale, on_change).run()


def launch_play(args):
    if args.invite and (args.fixture or args.sandbox or args.line or not Path(args.db).is_file()):
        raise ValueError('Local invitation redemption requires an existing save and interactive play.')
    if args.splash:
        from hube_tag import splash
        from hube_tag.io import read_json
        if not splash(
            read_json(args.splash), duration=args.splash_duration,
            renderer=args.splash_renderer, prompt=translator(args.locale)('> PRESS ENTER'),
        ):
            return 0
    game = Game.load(args.db) if Path(args.db).exists() else load_fixture()
    on_change = None
    if not args.sandbox:
        game.save(args.db)
        def on_change(session):
            session.save(args.db)
    options = {'locale': args.locale, 'hot_seat': args.hot_seat, 'on_change': on_change}
    if args.fixture is None:
        from .mission_terminal import run_mission
        run_mission(game, **options, sandbox=args.sandbox, fullscreen=not args.line, invite=args.invite)
    else:
        from .play import run_play
        run_play(game, **options)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Hube terminal MVP 0.1')
    parser.add_argument('--db', default='.hube.sqlite', help='SQLite event log')
    parser.add_argument('--locale', choices=['en', 'it'], default='en')
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('start', help='Legacy development hot-seat client')
    start.add_argument('fixture', choices=['hube-stop-01'])
    commands.add_parser('resume')
    play = commands.add_parser('play')
    play.add_argument('fixture', nargs='?', choices=['hube-stop-01'],
                      help='name the fixture to use the original STOP 01 menu')
    play.add_argument('--splash', type=Path, metavar='TRAJECTORIES.json', help='Animate a reconstructed tag before play')
    play.add_argument('--splash-duration', type=float, default=6, help='Splash display duration in seconds')
    play.add_argument('--splash-renderer', choices=['ascii', 'unicode', 'braille'], default='braille')
    play.add_argument('--hot-seat', action='store_true', help='Enable explicit development identity switching')
    play.add_argument('--line', action='store_true', help='Use the line-based mission client')
    play.add_argument('--sandbox', action='store_true', help='Play a disposable copy without saving')
    play.add_argument('--invite', metavar='TOKEN', help='Redeem a contextual invitation on this local save')
    journey = commands.add_parser('journey')
    journey.add_argument('--target', default='event_001')
    journey.add_argument('--at', type=int)
    journey.add_argument('--json', action='store_true')
    for view in ('timeline', 'network', 'people', 'places', 'resources', 'requirements', 'actions', 'log', 'world', 'ecosystem'):
        query = commands.add_parser(view)
        query.add_argument('--at', help='Event transaction number, e.g. 004 or T4')
        query.add_argument('--time', help='ISO timestamp with timezone')
    commands.add_parser('replay')
    from .replay import add_replay_arguments, play_simulation
    simulation = commands.add_parser('simulate')
    simulation.add_argument('fixture', choices=['hube-stop-01'])
    add_replay_arguments(simulation)
    args = parser.parse_args(argv)
    try:
        if args.command == 'simulate':
            play_simulation(args.fixture, mode=args.mode, speed=args.speed, locale=args.locale, recap=args.recap)
        elif args.command == 'play':
            return launch_play(args)
        elif args.command == 'journey':
            from .recap import render_journey
            trace = Game.load(args.db).project_journey(args.target, at=args.at)
            if args.json:
                print(json.dumps(trace, ensure_ascii=False, indent=2))
            else:
                render_journey(trace, locale=args.locale)
        elif args.command == 'start':
            if Path(args.db).exists():
                raise ValueError('game_already_exists_use_resume')
            game = load_fixture(args.fixture)
            game.save(args.db)
            run_session(game, locale=args.locale, on_change=lambda g: g.save(args.db))
        elif args.command == 'resume':
            run_session(Game.load(args.db), locale=args.locale, on_change=lambda g: g.save(args.db))
        else:
            game = Game.load(args.db)
            if args.command == 'replay':
                print(json.dumps(game.replay().get_world(), ensure_ascii=False, indent=2))
            else:
                at = int(args.at.lstrip('Tt')) if args.at else None
                projection = game.project(args.command, at=at, time=args.time)
                if args.command == 'timeline':
                    render_timeline(projection, sys.stdout, translator(args.locale))
                else:
                    print(json.dumps(projection, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
