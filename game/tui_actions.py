"""Present Hube's existing action forms inside the full-screen client."""

from io import StringIO
import re

from .capacity import capacity_mismatches
from .mission_terminal import MissionTerminal
from .tui_screen import ScreenDialogue
from .tui_capacity_forms import FORMS, mission_offer

MENU_LINE = re.compile(r'^\s*(\d+)\s{2,}(.+)')


class MissionActions(MissionTerminal):
    def __init__(self, game, screen, locale, on_change, **options):
        super().__init__(game, StringIO(), StringIO(), locale, on_change, **options)
        self.screen = screen
        self._ = screen._
        self.lines = []

    def take_lines(self):
        lines, self.lines = self.lines, []
        return lines

    def write(self, text=''):
        self.lines.append(str(text))

    def form(self, builder):
        return ScreenDialogue(self.screen, self.take_lines()).run(builder)

    def ask(self, prompt):
        entries, lines = [], []
        for line in self.take_lines():
            match = MENU_LINE.match(line)
            if match:
                entries.append((match[2], match[1]))
            elif line != self._('b / 0  Back'):
                lines.append(line)
        if entries:
            selected, _ = self.screen.choose('Work on this condition', entries, lines)
            return selected or 'b'
        return self.screen.text(prompt, lines) or ''

    def describe_need(self, need):
        world = self.game.get_world()
        recorded = len(need['offers'])
        compatible = sum(offer['compatible'] for offer in need['offers'])
        lines = [
            self._('Recorded offers · {recorded}').format(recorded=recorded),
            self._('Compatible offers · {compatible}').format(compatible=compatible),
            self._(
                'Confirmed · {committed}/{minimum}   Verified · {verified}/{minimum}'
            ).format(**need),
        ]
        for offer in need['offers']:
            label = self.support_label(offer, world['nodes'])
            mismatches = capacity_mismatches(world, offer, need['demand'])
            reasons = [self._(reason) for reason in mismatches]
            if not reasons and offer['available_for_need'] == 0:
                reasons.append(self._('already allocated to another need'))
            lines.append(label + (' · ' + ', '.join(reasons) if reasons else ''))
        return lines

    def show_need(self, demand_id):
        need = self.game.project_need(demand_id)
        self.write(self._(need['resource']['label']))
        for line in self.describe_need(need):
            self.write(line)
        return need

    def capacity(self, d, kind, need=None):
        builder = (
            FORMS.get(need['unit'])
            if need and need['demand']['kind'] == 'requires'
            else None
        )
        if builder and kind == 'offer':
            return mission_offer(self, d, need, builder)
        return super().capacity(d, kind, need)

    def ask_person(self, demand_id):
        from .tui_requests import create_request

        create_request(self, demand_id)

    def work_on_condition(self, demand_id):
        if self.game.project_need(demand_id)['unit'] != 'confirmation':
            return super().work_on_condition(demand_id)
        from .tui_presentations import propose, show_presentations
        from .tui_requests import create_request

        choices = [
            ('Propose a presentation', lambda: propose(self)),
            ('Declare my availability', lambda: self.offer_date(demand_id)),
            ('Ask someone to confirm a date', lambda: create_request(self, demand_id)),
            ('Explore existing proposals', lambda: show_presentations(self)),
            ('Review offers and commitments', lambda: self.work_on(demand_id)),
        ]
        chosen, _ = self.screen.choose(
            'Date', [(self._(label), action) for label, action in choices]
        )
        if chosen:
            chosen()

    def offer_date(self, demand_id):
        need = self.game.project_need(demand_id)
        result = self.collect_and_submit(lambda d: self.capacity(d, 'offer', need))
        if result and result['ok']:
            self.screen.read(
                'Date', self.describe_need(self.game.project_need(demand_id))
            )

    def ensure_player(self):
        if self.session is not None:
            return True
        selected = self.choose_identity()
        notes = self.take_lines()
        if not selected and notes:
            self.screen.notice = notes[-1]
        return selected

    def submit_command(self, command):
        result = super().submit_command(command)
        notes = self.take_lines()
        self.screen.notice = notes[-1] if notes else ''
        if not result['ok'] or len(notes) > 1:
            self.screen.read('Action result', notes)
        return result
