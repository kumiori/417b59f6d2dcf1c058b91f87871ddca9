"""Navigable terminal forms. Builders collect data; they never mutate the world.

On back, replay only cached answers before the previous question. Later answers
are discarded. This permits branching forms without replaying submitted commands.
"""
from datetime import date


class Cancelled(Exception):
    pass


class Back(Exception):
    pass


_MISSING = object()


class Dialogue:
    def __init__(self, source, output, translate=lambda text: text):
        self.source, self.output, self._ = source, output, translate
        self.answers = []
        self.cursor = 0

    def write(self, text):
        self.output.write(str(text) + '\n')
        self.output.flush()

    def run(self, builder):
        self.answers = []
        self.write(self._('b: back one step · 0: cancel action · ?: help'))
        while True:
            self.cursor = 0
            try:
                return builder(self)
            except Back:
                if self.cursor == 0:
                    return None
                self.answers = self.answers[:self.cursor - 1]
            except Cancelled:
                return None

    def _field(self, render, parse, default=_MISSING, error='Invalid input; please try again.',
               *, keep_default=False):
        if self.cursor < len(self.answers):
            value = self.answers[self.cursor]
            self.cursor += 1
            return value
        while True:
            render()
            raw = self.source.readline()
            if not raw:
                raise EOFError
            raw = raw.strip()
            if raw == '0':
                raise Cancelled
            if raw.lower() == 'b':
                raise Back
            if raw == '?':
                self.write(self._('Enter a value for this question. b goes back; 0 cancels this action. No changes are saved until the form is complete.'))
                continue
            try:
                supplied = default if raw == '' and default is not _MISSING else raw
                value = default if keep_default and raw == '' and default is not _MISSING else parse(supplied)
            except (ValueError, TypeError, IndexError):
                self.write(self._(error))
                continue
            self.answers.append(value)
            self.cursor += 1
            return value

    def choose(self, prompt, options, label=lambda item: item):
        if not options:
            self.write(self._('No options available.'))
            raise Cancelled
        def render():
            self.write(self._(prompt))
            for i, item in enumerate(options, 1):
                self.write(f'  {i}  {label(item)}')
            self.write('>')
        def parse(raw):
            number = int(raw)
            if not 1 <= number <= len(options):
                raise ValueError
            return options[number - 1]
        return self._field(render, parse, error='I need one of the listed choices.')

    def text(self, prompt, *, default=_MISSING, parse=None, error='Please enter a nonempty value.',
             keep_default=False):
        def render():
            suffix = f' [{default}]' if default is not _MISSING else ''
            self.write(self._(prompt) + suffix)
        def nonempty(raw):
            if not raw.strip():
                raise ValueError
            return raw
        return self._field(render, parse or nonempty, default, error, keep_default=keep_default)

    def quantity(self, prompt='Quantity?'):
        def positive(raw):
            value = int(raw)
            if value <= 0:
                raise ValueError
            return value
        return self.text(prompt, parse=positive, error='Quantity must be a positive integer.')

    def date(self, prompt, *, default, minimum=None):
        def valid(raw):
            value = date.fromisoformat(raw).isoformat()
            if minimum is not None and value < minimum:
                raise ValueError
            return value
        return self.text(prompt, default=default, parse=valid, error='Enter a valid date, not earlier than the start date (YYYY-MM-DD).')

    def yes(self, prompt, *, default=False):
        def boolean(raw):
            if raw.casefold() in {'y', 'yes', 's', 'si', 'sì'}:
                return True
            if raw.casefold() in {'n', 'no'}:
                return False
            raise ValueError
        return self.text(prompt, default='y' if default else 'n', parse=boolean, error='Please answer y or n.')
