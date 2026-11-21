"""Hube controls composed from Game-Gamer's bounded terminal viewport."""

from game_gamer.tui.screen import Screen

from .dialogue import Back, Cancelled, Dialogue, _MISSING

RETURN = {'esc', 'b', '0'}


class MissionScreen:
    def __init__(self, viewport, translate, context):
        self.viewport = viewport
        self._ = translate
        self.context = context
        self.notice = ''

    def draw(
        self,
        title,
        lines,
        *,
        entries=(),
        selected=0,
        footer='',
        scroll=0,
        fixed=False,
        styles=(),
    ):
        return self.viewport.draw(
            Screen(
                'HUBE',
                list(lines),
                list(entries),
                self._(footer),
                selected,
                scroll,
                navigation=False,
                breadcrumb=self._(title),
                reveal=bool(entries),
                wrap_entries=True,
                raster_start=0 if fixed else None,
                styles=list(styles),
            ),
            self.context(),
            self.notice,
        )

    def key(self):
        return self.viewport.key()

    def help(self, lines):
        self.read('Help', lines, allow_help=False)

    def choose(self, title, entries, lines=(), *, extra=(), index=0, reset=False):
        """Return the selected value and position, or an explicit screen shortcut."""
        footer = '↑↓ Navigate · Enter Select · Esc/b Back · ? Help'
        if reset:
            footer += ' · r Reset view'
        if extra:
            footer += ' · ' + ' · '.join(label for _, label in extra)
        shortcuts = dict(extra)
        while True:
            self.draw(title, lines, entries=entries, selected=index, footer=footer)
            key = self.key()
            if key in RETURN:
                return None, index
            if key in shortcuts:
                return key, index
            if key == 'r' and reset:
                index = 0
            elif key == '?':
                self.help([self._(footer)])
            elif key in {'up', 'down'} and entries:
                index = (index + (1 if key == 'down' else -1)) % len(entries)
            elif key == 'enter' and entries:
                return entries[index][1], index
            elif isinstance(key, str) and key.isascii() and key.isdecimal():
                if 1 <= int(key) <= len(entries):
                    return entries[int(key) - 1][1], int(key) - 1

    def read(self, title, lines, *, allow_help=True):
        scroll = 0
        footer = '↑↓ Scroll · Esc/b Back'
        if allow_help:
            footer += ' · ? Help'
        while True:
            scroll = self.draw(title, lines, footer=footer, scroll=scroll)
            key = self.key()
            if key in RETURN | {'enter'}:
                return
            if key in {'up', 'down', 'pageup', 'pagedown'}:
                step = (
                    max(1, self.viewport.size()[1] - 8) if key.startswith('page') else 1
                )
                scroll = max(
                    0, scroll + (step if key in {'down', 'pagedown'} else -step)
                )
            elif key == '?' and allow_help:
                self.help([self._(footer)])

    def text(self, title, lines):
        value = ''
        while True:
            width, height = self.viewport.size()
            shown = '› ' + value[-max(1, width // 2) :]
            self.draw(
                title,
                [*lines, '', shown],
                scroll=max(0, len(lines) + 8 - height),
                footer='Enter Keep · Esc Back · F1 Help',
            )
            key = self.key()
            if key == 'enter':
                return value
            if key == 'esc':
                return None
            if key == self.viewport.curses.KEY_F1:
                self.help(
                    [
                        self._(
                            'Enter keeps the text. Esc returns to the previous screen.'
                        ),
                        self._('Letters and punctuation are entered literally.'),
                    ]
                )
            elif key in {self.viewport.curses.KEY_BACKSPACE, '\x7f', '\b'}:
                value = value[:-1]
            elif isinstance(key, str) and len(key) == 1 and key.isprintable():
                value += key


class ScreenDialogue(Dialogue):
    """Use the existing action builders with screen-based input and backtracking."""

    def __init__(self, screen, lines):
        super().__init__(None, None, screen._)
        self.screen = screen
        self.lines = lines

    def write(self, text):
        # Dialogue.run's line-client control legend is replaced by the screen footer.
        pass

    def _answer(self, collect):
        if self.cursor == len(self.answers):
            self.answers.append(collect())
        answer = self.answers[self.cursor]
        self.cursor += 1
        return answer

    def choose(self, prompt, options, label=lambda item: item):
        if not options:
            self.screen.read(prompt, [*self.lines, self._('No options available.')])
            raise Cancelled

        def collect():
            entries = [(label(item), i) for i, item in enumerate(options)]
            selected, _ = self.screen.choose(prompt, entries, self.lines)
            if selected is None:
                raise Back
            return options[selected]

        return self._answer(collect)

    def text(
        self,
        prompt,
        *,
        default=_MISSING,
        parse=None,
        error='Please enter a nonempty value.',
        keep_default=False,
    ):
        def collect():
            lines = list(self.lines)
            if default is not _MISSING:
                lines.append(
                    self._('Press Enter to keep {value}.').format(value=default)
                )
            while True:
                raw = self.screen.text(prompt, lines)
                if raw is None:
                    raise Back
                supplied = default if raw == '' and default is not _MISSING else raw
                try:
                    if keep_default and raw == '' and default is not _MISSING:
                        return default
                    if parse:
                        return parse(supplied)
                    if supplied.strip():
                        return supplied.strip()
                except (ValueError, TypeError, IndexError):
                    pass
                lines = [*self.lines, self._(error)]

        return self._answer(collect)

    def yes(self, prompt, *, default=False):
        def collect():
            entries = [(self._('Yes'), True), (self._('No'), False)]
            if not default:
                entries.reverse()
            selected, _ = self.screen.choose(
                'Review', entries, [*self.lines, self._(prompt)]
            )
            if selected is None:
                raise Back
            return selected

        return self._answer(collect)
