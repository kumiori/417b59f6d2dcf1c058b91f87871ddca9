"""Goal-directed local play. Forms collect commands; the engine owns semantics."""
import sys
from .terminal import Terminal, render_timeline
from .player import PlayerSession
from .recap import offer_recap
from .dialogue import Dialogue
from .model import NODE_KINDS, OBSERVATION_KINDS, relation_valid


class PlayTerminal(Terminal):
    def __init__(self, game, source, output, locale='en', on_change=None, *, hot_seat=False):
        super().__init__(game, source, output, locale, on_change)
        self.hot_seat, self.session = hot_seat, None
        self.dialogue = Dialogue(source, output, self._)

    def form(self, builder):
        return self.dialogue.run(builder)

    def key(self):
        return f"play-{len(self.game.project('log'))+1:06}"

    def choose_identity(self):
        people = [n for n in self.game.project('people') if n['metadata'].get('playable')]
        def collect(d):
            person = d.choose('Choose who you are:', people[:3] + [None] + people[3:],
                              lambda n: n['label'] if n else self._('Join as someone else'))
            return {'person': person, 'label': d.text('Name?') if person is None else None}
        selection = self.form(collect)
        if selection is None:
            return False
        person = selection['person']
        if person is None:
            result = self.game.join(selection['label'], key=self.key())
            if not result['ok']:
                self.write(self._(result['errors'][0]))
                return False
            if self.on_change:
                self.on_change(self.game)
            person_id = self.game.get_world()['actions'][result['action_id']]['target_ids'][0]
            person = self.game.get_world()['nodes'][person_id]
        if self.session is None:
            self.session = PlayerSession(self.game, person['id'], hot_seat=self.hot_seat)
        else:
            self.session.switch(person['id'])
        self.actor = self.session.actor
        self.write(self._('You are {name}.').format(name=person['label'].upper()))
        self.write(self._('{count} requests are waiting for you.').format(count=len(self.session.inbox())))
        return True

    def submit_command(self, command):
        result = self.session.submit({'key': self.key(), **command})
        if not result['ok']:
            self.write(self._('Command rejected.') + ' ' + ', '.join(self._(e) for e in result['errors']))
            return result
        if self.on_change:
            self.on_change(self.game)
        self.write(self._('World changed.'))
        world = self.game.get_world()
        for mutation in result['mutations']:
            r = mutation['after']
            if mutation['entity_type'] == 'relation':
                source, target = world['nodes'][r['source_id']]['label'], world['nodes'][r['target_id']]['label']
                self.write(f"{source} ──{self._(r['kind'])}──▶ {target} ({self._(r['status'])})")
        if command['kind'] == 'request':
            self.write(self._('WAITING — the recipient must respond.'))
        elif command['kind'] == 'observe':
            self.write(self._('Information recorded. This is not an offer or a commitment.'))
        return result

    def collect_and_submit(self, builder):
        command = self.form(builder)
        return self.submit_command(command) if command is not None else None

    def resource_label(self, node):
        matches = self.game.resolve_resources(node['label'])
        candidate = next(n for n in matches if n['id'] == node['id'])
        text = node['label']
        if candidate['required_by']:
            owners = [self.game.get_world()['nodes'][nid]['label'] for nid in candidate['required_by']]
            text += ' — ' + self._('required by') + ' ' + ', '.join(owners)
        if len(matches) > 1:
            if not candidate['required_by']:
                text += ' — ' + self._('separate resource, not this event’s requirement')
            text += f" [{node['id']}]"
        return text

    def new_resource(self, d):
        label = d.text('Resource name?')
        candidates = self.game.resolve_resources(label)
        if candidates:
            candidate = d.choose('This may already exist:', candidates + [None],
                                  lambda n: self.resource_label(n) if n else self._('Create a different resource called "{name}"').format(name=label))
            if candidate:
                return {'resource_id': candidate['id']}
            return {'resource_label': label, 'allow_duplicate_resource': True}
        return {'resource_label': label}

    def resource(self, d):
        nodes = [n for n in self.game.project('resources') if n['kind'] == 'resource']
        required_ids = {r['target_id'] for r in self.game.get_world()['relations'].values() if r['kind'] == 'requires'}
        nodes.sort(key=lambda n: n['id'] not in required_ids)
        selected = d.choose('Resource category?', nodes + [None], lambda n: self.resource_label(n) if n else self._('New resource'))
        return {'resource_id': selected['id']} if selected else self.new_resource(d)

    def location(self, d):
        place = d.choose('Where?', self.game.project('places') + [None], lambda n: n['label'] if n else self._('New place'))
        return {'location_id': place['id']} if place else {'location_label': d.text('Place name?')}

    def asset(self, d, location, *, required=False):
        nodes = list(self.game.get_world()['nodes'].values())
        allowed = {'place'} if required else {'place', 'object'}
        options = [n for n in nodes if n['kind'] in allowed and n['id'] != location.get('location_id')]
        asset = d.choose('Which venue?' if required else 'Which specific place or object?', options + [None],
                         lambda n: n['label'] if n else self._('New venue' if required else 'New place or object'))
        if asset:
            return {'asset_id': asset['id']}
        kind = 'place' if required else d.choose('Type?', ['place', 'object'], self._)
        return {'asset_label': d.text('Venue name?' if required else 'Name?'), 'asset_kind': kind}

    def capacity(self, d, kind, need=None):
        command = {'kind': kind}
        command.update({'resource_id': need['resource']['id']} if need else self.resource(d))
        unit = need['unit'] if need else None
        command['quantity'] = d.quantity('How many people can you host?' if kind == 'offer' and unit == 'bed' else 'Quantity?')
        if unit is None:
            resource_id = command.get('resource_id')
            related = next((r for r in self.game.get_world()['relations'].values()
                            if r['kind'] in {'requires', 'needs'} and r['target_id'] == resource_id), None)
            unit = d.text('Unit? (for example bed, hour, eur)', **({'default': related['attributes']['unit']} if related else {}))
        command['unit'] = unit
        location = self.location(d)
        command.update(location)
        target = self.game.get_world()['nodes']['event_001']
        dates = need['demand']['attributes'] if need else {}
        start = d.date('Available from (YYYY-MM-DD)?', default=dates.get('available_from', target['metadata']['proposed_date']))
        end = d.date('Available until (YYYY-MM-DD)?', default=max(start, dates.get('available_until', target['metadata']['proposed_date'])), minimum=start)
        command.update(available_from=start, available_until=end)
        required_asset = need and need['demand']['attributes'].get('required_asset_kind')
        if kind == 'offer' and (required_asset or d.yes('Attach a specific place or object? Optional.', default=False)):
            command.update(self.asset(d, location, required=bool(required_asset)))
        return command

    def observation_target(self, d, kinds):
        nodes = [n for n in self.game.get_world()['nodes'].values() if n['kind'] in kinds]
        target = d.choose('Choose the subject of this observation.', nodes + [None],
                          lambda n: self.resource_label(n) if n and n['kind'] == 'resource' else n['label'] if n else self._('Something new'))
        if target:
            return {'target_id': target['id']}, target['kind']
        kind = next(iter(kinds)) if len(kinds) == 1 else d.choose('Type?', sorted(kinds), self._)
        if kind == 'resource':
            resource = self.new_resource(d)
            if resource.get('resource_id'):
                return {'target_id': resource['resource_id']}, kind
            return {'node_kind': kind, 'label': resource['resource_label'],
                    **({'allow_duplicate_resource': True} if resource.get('allow_duplicate_resource') else {})}, kind
        return {'node_kind': kind, 'label': d.text('Name?')}, kind

    def observation(self, d):
        categories = ['A person or group', 'A need / resource', 'A place', 'The event', 'An object', 'A relationship', 'Something new']
        category = d.choose('What is your observation about?', categories, self._)
        source_id = self.actor
        if category == 'A relationship':
            source_id = d.choose('Choose the source.', list(self.game.get_world()['nodes'].values()), lambda n: n['label'])['id']
            kinds = NODE_KINDS
        else:
            kinds = {'A person or group': {'person', 'collective'}, 'A need / resource': {'resource'}, 'A place': {'place'},
                     'The event': {'event'}, 'An object': {'object'}, 'Something new': NODE_KINDS}[category]
        payload, target_kind = self.observation_target(d, kinds)
        source_kind = self.game.get_world()['nodes'][source_id]['kind']
        if category == 'A relationship':
            valid = [k for k in OBSERVATION_KINDS if relation_valid(k, source_kind, target_kind)]
            relation = d.choose('Relationship?', valid, self._)
        else:
            relation = 'knows' if target_kind in {'person', 'collective'} else 'suggests'
        return {'kind': 'observe', 'source_id': source_id, 'relation_kind': relation, **payload}

    def correction(self, d):
        world = self.game.get_world()
        own = [r for r in world['relations'].values() if r['created_by'] == self.actor and r['status'] == 'reported' and r['kind'] in OBSERVATION_KINDS]
        old = d.choose('Correct one of your reported observations.', own, self.commitment_label)
        nodes = list(world['nodes'].values())
        sources = [n for n in nodes if any(relation_valid(old['kind'], n['kind'], t['kind']) for t in nodes)]
        source = d.choose('Correct source?', sources, lambda n: n['label'])
        targets = [n for n in nodes if relation_valid(old['kind'], source['kind'], n['kind'])]
        target = d.choose('Correct target?', targets, lambda n: n['label'])
        return {'kind': 'correct', 'subject': old['id'], 'source_id': source['id'], 'target_id': target['id'], 'reason': d.text('Reason?')}

    def add(self):
        def collect(d):
            choice = d.choose('Add something to the world', ['Share an observation', 'Offer something', 'Report a need', 'Propose something', 'Correct something', 'Introduce people', 'Withdraw something', 'Decline a proposed connection'], self._)
            if choice == 'Share an observation':
                return self.observation(d)
            if choice in {'Offer something', 'Report a need'}:
                return self.capacity(d, 'offer' if choice == 'Offer something' else 'need')
            if choice == 'Propose something':
                return {'kind': 'propose', 'label': d.text('What do you propose?')}
            if choice == 'Correct something':
                return self.correction(d)
            if choice in {'Withdraw something', 'Decline a proposed connection'}:
                states = {'proposed'} if choice == 'Decline a proposed connection' else {'reported', 'proposed', 'committed', 'verified'}
                relations = [r for r in self.game.get_world()['relations'].values() if r['source_id'] == self.actor and r['status'] in states and r['kind'] in {'offers', 'needs', 'satisfies', 'proposes'}]
                subject = d.choose('Choose a subject.', relations, self.commitment_label)
                return {'kind': 'reject' if choice == 'Decline a proposed connection' else 'withdraw', 'subject': subject['id'], 'reason': d.text('Reason?')}
            people = self.game.project('people')
            source = d.choose('Introduce whom?', people, lambda n: n['label'])
            target = d.choose('To whom?', [p for p in people if p['id'] != source['id']], lambda n: n['label'])
            return {'kind': 'introduce', 'source_id': source['id'], 'target_id': target['id']}
        result = self.collect_and_submit(collect)
        if result and result['ok']:
            self.after_offer(result)

    def show_need(self, demand_id):
        need = self.game.project_need(demand_id)
        self.write(need['resource']['label'].upper() + (' ✓' if need['verified'] >= need['minimum'] else ''))
        self.write(self._('{verified} / {minimum} {unit} secured.').format(**{**need, 'unit': self._(need['unit'])}))
        self.write(self._('Offered: {offered}/{minimum} · committed: {committed}/{minimum} · verified: {verified}/{minimum}').format(**need))
        self.write(self._('Known offers'))
        world = self.game.get_world()
        if not need['offers']:
            self.write('  ' + self._('none'))
        for offer in need['offers']:
            a = offer['attributes']
            text = f"  {world['nodes'][offer['source_id']]['label']}: {a['quantity']} {self._(a['unit'])} · {world['nodes'][a['location_id']]['label']} · {a['available_from']} → {a['available_until']}"
            if not offer['compatible']:
                text += ' — ' + self._('different constraints; not currently a match')
            elif offer['available_for_need'] == 0:
                text += ' — ' + self._('already allocated to another need')
            self.write(text)
        return need

    def confirm(self, subject):
        if self.form(lambda d: d.yes('Confirm your commitment?', default=True)):
            self.submit_command({'kind': 'confirm', 'subject': subject})

    def connect(self, move):
        result = self.submit_command({'kind': 'act', 'possibility_id': move['id']})
        if result['ok']:
            commitment = next(m['after'] for m in result['mutations'] if m['entity_type'] == 'relation' and m['after']['kind'] == 'satisfies')
            if commitment['source_id'] == self.actor:
                self.confirm(commitment['id'])
            else:
                self.write(self._('WAITING — the provider must confirm their commitment.'))

    def after_offer(self, result, demand_id=None):
        offers = [m['after']['id'] for m in result['mutations'] if m['entity_type'] == 'relation' and m['before'] is None and m['after']['kind'] == 'offers']
        if not offers:
            return
        if demand_id:
            self.show_need(demand_id)
        moves = [p for p in self.session.possible_moves(demand_id=demand_id) if p['source_ids'][0] in offers]
        if not moves:
            self.write(self._('Offer recorded. No matching move yet; check dates, location, unit and any required venue.'))
            return
        self.write(self._('NEW POSSIBILITY'))
        for move in moves:
            self.write(self.possibility_label(move))
        if self.form(lambda d: d.yes('Connect this offer?', default=True)):
            move = moves[0] if len(moves) == 1 else self.form(lambda d: d.choose('Which need should it support?', moves, self.possibility_label))
            if move:
                self.connect(move)

    def ask_person(self, demand_id):
        moves = [m for m in self.session.possible_moves(demand_id=demand_id, explore=True) if m['kind'] == 'ask']
        world = self.game.get_world()
        move = self.form(lambda d: d.choose('Who would you like to ask?', moves, lambda m: world['nodes'][m['source_ids'][0]]['label']))
        if move:
            self.submit_command(move['suggested_commands'][0])

    def know_person(self, demand_id):
        def collect(d):
            payload, _ = self.observation_target(d, {'person'})
            return {'kind': 'observe', 'relation_kind': 'knows', **payload}
        result = self.collect_and_submit(collect)
        if not result or not result['ok']:
            return
        relation = next(m['after'] for m in result['mutations'] if m['entity_type'] == 'relation')
        if self.form(lambda d: d.yes('Ask this person about the condition?', default=True)):
            self.submit_command({'kind': 'request', 'recipient_id': relation['target_id'], 'demand_id': demand_id, 'via_relation_id': relation['id']})

    def verify(self, allocations):
        def collect(d):
            subject = d.choose('Which commitment can you verify?', allocations, self.commitment_label)
            evidence = d.choose('Evidence?', ['organizer_confirmation', 'player_confirmation', 'artifact', 'self_report'], self._)
            return {'kind': 'verify', 'subject': subject['id'], 'evidence_kind': evidence, 'reference': d.text('Evidence reference or note?')}
        self.collect_and_submit(collect)

    def work_on(self, demand_id):
        while not self.game.project('now')['feasible']:
            need = self.show_need(demand_id)
            moves = self.session.possible_moves(demand_id=demand_id)
            mine = [r for r in need['allocations'] if r['source_id'] == self.actor and r['status'] == 'proposed']
            verifiable = [r for r in need['allocations'] if r['source_id'] != self.actor and r['status'] == 'committed']
            for i, label in enumerate(['I can provide this', 'Someone else can provide it', 'I know someone who might', 'Ask someone', 'Add information'], 1):
                self.write(f'  {i}  ' + self._(label))
            if moves:
                self.write('  6  ' + self._('Connect a known offer'))
            if mine:
                self.write('  7  ' + self._('Confirm my commitment'))
            if verifiable:
                self.write('  8  ' + self._('Verify a commitment'))
            self.write(self._('b / 0  Back'))
            choice = self.ask('>')
            if choice in {'0', 'b'}:
                return
            if choice == '1':
                result = self.collect_and_submit(lambda d: self.capacity(d, 'offer', need))
                if result and result['ok']:
                    self.after_offer(result, demand_id)
            elif choice in {'2', '4'}:
                self.write(self._('Ask them to confirm what they can offer. This does not offer on their behalf.'))
                self.ask_person(demand_id)
            elif choice == '3':
                self.know_person(demand_id)
            elif choice == '5':
                self.collect_and_submit(lambda d: {'kind': 'observe', 'target_id': need['resource']['id'], 'relation_kind': 'suggests', 'note': d.text('What do you know about this condition?')})
            elif choice == '6' and moves:
                move = self.form(lambda d: d.choose('Connect which offer?', moves, self.possibility_label))
                if move:
                    self.connect(move)
            elif choice == '7' and mine:
                subject = self.form(lambda d: d.choose('Confirm which commitment?', mine, self.commitment_label))
                if subject:
                    self.submit_command({'kind': 'confirm', 'subject': subject['id']})
            elif choice == '8' and verifiable:
                self.verify(verifiable)
            elif choice == '?':
                self.write(self._('Work on this condition: offer, ask, connect, confirm, then verify as another player.'))
            else:
                self.write(self._('I need one of the listed choices.'))

    def possible_now(self):
        moves = self.session.possible_moves()
        self.write(self._('POSSIBLE NOW'))
        if moves:
            move = self.form(lambda d: d.choose('Connect which offer?', moves, self.possibility_label))
            if move:
                self.connect(move)
        else:
            self.write(self._('No grounded matches yet. Offer something, add what you know, or explore one unmet need.'))
        if self.form(lambda d: d.yes('Explore unanswered needs?', default=False)):
            demands = self.active_needs()
            demand = self.form(lambda d: d.choose('What do you want to work on?', demands, self.need_label))
            if demand:
                self.work_on(demand['id'])

    def active_needs(self):
        return [r for r in self.game.get_world()['relations'].values() if r['kind'] in {'needs', 'requires'} and r['status'] not in {'withdrawn', 'rejected'}
                and self.game.project_need(r['id'])['verified'] < r['attributes']['quantity']]

    def need_label(self, demand):
        resource = self.game.get_world()['nodes'][demand['target_id']]['label']
        a = demand['attributes']
        return f"{resource} — {a['quantity']} {self._(a['unit'])}"

    def look(self):
        for view, label in [('people', 'People'), ('places', 'Places'), ('resources', 'Resources')]:
            self.write(self._(label))
            for node in self.game.project(view):
                self.write('  ' + (self.resource_label(node) if node['kind'] == 'resource' else node['label']))

    def requests(self):
        world = self.game.get_world()
        def label(r):
            demand = world['relations'][r['attributes']['demand_id']]
            return self._('{name} asks about {resource}.').format(name=world['nodes'][r['source_id']]['label'], resource=world['nodes'][demand['target_id']]['label'])
        def collect(d):
            request = d.choose('Requests waiting for you', self.session.inbox(), label)
            response = d.choose('Your response?', ['accept', 'decline', 'modify'], self._)
            command = {'kind': 'respond', 'subject': request['id'], 'response': response}
            if response == 'modify':
                field = d.choose('What would you change?', ['quantity', 'dates', 'location', 'asset', 'unit'], self._)
                if field == 'quantity':
                    command['quantity'] = d.quantity()
                elif field == 'dates':
                    command['available_from'] = d.date('Available from (YYYY-MM-DD)?', default=request['attributes']['available_from'])
                    command['available_until'] = d.date('Available until (YYYY-MM-DD)?', default=max(command['available_from'], request['attributes']['available_until']), minimum=command['available_from'])
                elif field in {'location', 'asset'}:
                    options = self.game.project('places')
                    if field == 'asset':
                        options = [n for n in options if n['id'] != request['attributes']['location_id']]
                    command['location_id' if field == 'location' else 'asset_id'] = d.choose('Where?', options, lambda n: n['label'])['id']
                else:
                    command['unit'] = d.text('Unit? (for example bed, hour, eur)')
            return command
        result = self.collect_and_submit(collect)
        if result and result['ok']:
            request = next(m['after'] for m in result['mutations'] if m['entity_type'] == 'relation' and m['after']['kind'] == 'requested')
            self.after_offer(result, request['attributes']['demand_id'])

    def run(self):
        self.write('HUBE / STOP 01')
        try:
            if not self.choose_identity():
                return self.game
            while not self.game.project('now')['feasible']:
                self.status()
                self.write(self.game.get_world()['nodes'][self.actor]['label'].upper())
                required = [r for r in self.game.project('requirements') if r['required'] and r['status'] != 'satisfied' and 'demand_id' in r['rule']]
                choices = [('need', r['rule']['demand_id']) for r in required]
                self.write(self._('WHAT NEEDS TO BECOME TRUE'))
                for i, requirement in enumerate(required, 1):
                    self.write(f"  {i}  {self._(requirement['metadata']['label'])}")
                self.write(self._('WHAT ELSE CAN I DO'))
                for action, label in [('add', 'Add something to the world'), ('possible', 'See new possibilities'), ('look', 'Look around'), ('history', 'History')]:
                    choices.append((action, None))
                    self.write(f'  {len(choices)}  ' + self._(label))
                other = [d for d in self.active_needs() if d['kind'] == 'needs']
                if other:
                    self.write(self._('OTHER NEEDS DISCOVERED DURING PLAY (not ending conditions)'))
                    for demand in other:
                        choices.append(('need', demand['id']))
                        self.write(f'  {len(choices)}  ' + self.need_label(demand))
                self.write(self._('r  Requests · 0  Save and exit · ?  Help'))
                if self.hot_seat:
                    self.write(self._('s  Switch player — development hot-seat mode'))
                raw = self.ask('>')
                if raw == '0':
                    break
                if raw == 'r':
                    self.requests()
                elif raw == 's' and self.hot_seat:
                    self.choose_identity()
                elif raw == '?':
                    self.write(self._('Choose an unresolved condition to work on. New needs stay separate from the ending. In forms: b back, 0 cancel, ? help.'))
                elif raw.isdecimal() and 1 <= int(raw) <= len(choices):
                    action, target = choices[int(raw) - 1]
                    if action == 'need':
                        self.work_on(target)
                    elif action == 'add':
                        self.add()
                    elif action == 'possible':
                        self.possible_now()
                    elif action == 'look':
                        self.look()
                    else:
                        render_timeline(self.game.project('timeline'), self.output, self._)
                else:
                    self.write(self._('I need one of the listed choices.'))
            if self.game.project('now')['feasible']:
                self.status()
                offer_recap(self.game, self.source, self.output, self.locale)
        except EOFError:
            pass
        return self.game


def run_play(game, source=None, output=None, locale='en', on_change=None, *, hot_seat=False):
    return PlayTerminal(game, source if source is not None else sys.stdin,
                        output if output is not None else sys.stdout, locale, on_change, hot_seat=hot_seat).run()
