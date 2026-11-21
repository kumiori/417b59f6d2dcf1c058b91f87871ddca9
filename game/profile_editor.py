"""Local drafts and the two-column HUBE terminal profile editor."""
from copy import deepcopy
import locale
import os
import sys
import unicodedata

from game_gamer_semantics.assistant import suggested_keys
from game_gamer_semantics.declarations import DIRECTIONS, MAX_DESCRIPTION, same_content

from .declarations import PROFILE_DETAILS


DETAIL_LABELS = {'interests': 'Interests', 'capabilities': 'Capabilities'}
COLUMN_LABELS = {'offer': 'I OFFER', 'need': 'I SEEK'}


class ProfileDraft:
    def __init__(self, declarations, details):
        self.original = {key: row for key, row in declarations.items() if row['status'] == 'shared'}
        self.entries = {
            direction: [deepcopy(row) for row in self.original.values() if row['direction'] == direction]
            for direction in DIRECTIONS
        }
        self.original_details = {field: details.get(field, '') for field in PROFILE_DETAILS}
        self.details = self.original_details.copy()

    def add(self, direction):
        self.entries[direction].append({
            'direction': direction, 'description': '', 'categories': [], 'status': 'shared',
        })

    def incomplete(self):
        for direction, entries in self.entries.items():
            for index, row in enumerate(entries):
                if (row.get('id') or row['categories']) and not row['description'].strip():
                    return direction, index
        return None

    def state(self, row):
        if row is None:
            return 'No entry selected'
        if not row['description'].strip():
            return 'Description needed'
        original = self.original.get(row.get('id'))
        if original and same_content(original, row):
            return 'Saved entry'
        return 'Unsaved draft'

    def changes(self):
        changes = []
        seen = set()
        for entries in self.entries.values():
            for row in entries:
                identity = {}
                if 'id' in row:
                    seen.add(row['id'])
                    identity = {'id': row['id'], 'revision': row['revision']}
                    previous = self.original[row['id']]
                    if same_content(previous, row):
                        continue
                elif not row['description'] and not row['categories']:
                    continue
                if not row['description'].strip():
                    raise ValueError('Write a description for each entry, or remove the draft.')
                content = {field: row[field] for field in ('direction', 'description', 'categories')}
                changes.append({**identity, **content, 'status': 'shared'})
        for row in self.original.values():
            if row['id'] not in seen:
                changes.append({'id': row['id'], 'revision': row['revision'], 'status': 'withdrawn'})
        details = {field: value or None for field, value in self.details.items()
                   if value != self.original_details[field]}
        return changes, details


def supports_editor(source, output):
    return (source is sys.stdin and output is sys.stdout and os.name == 'posix'
            and os.environ.get('TERM', 'dumb') not in {'', 'dumb'}
            and source.isatty() and output.isatty())


def _width(char):
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in {'W', 'F'} else 1


def _fit(text, width):
    # Labels and historical descriptions can originate from a save.
    text = ''.join(char if char.isprintable() else ' ' for char in text)
    used = 0
    for index, char in enumerate(text):
        used += _width(char)
        if used > width:
            return text[:index]
    return text


class ProfileScreen:
    def __init__(self, screen, curses, draft, taxonomy, name, translate, assistant, *, host=None):
        self.screen, self.curses = screen, curses
        self.draft, self.taxonomy, self.name, self._ = draft, taxonomy, name, translate
        self.assistant = assistant
        self.host = host
        self.column = self.row = 0
        self.index = dict.fromkeys(DIRECTIONS, 0)
        retired = {key for row in draft.original.values() for key in row['categories']} - set(taxonomy.keys)
        self.keys = (*taxonomy.keys, *sorted(retired), None)
        self.notice = ''
        self.palette = {}
        if host:
            self.palette = profile_palette(host.viewport)
        elif curses.has_colors():
            curses.use_default_colors()
            mint, lavender, grey = (157, 183, 246) if curses.COLORS >= 256 else (curses.COLOR_GREEN, curses.COLOR_MAGENTA, curses.COLOR_WHITE)
            for index, (name, fg, bg) in enumerate([
                ('offer', mint, -1), ('need', lavender, -1), ('dim', grey, -1),
                ('offer_focus', curses.COLOR_BLACK, mint), ('need_focus', curses.COLOR_BLACK, lavender),
            ], 1):
                curses.init_pair(index, fg, bg)
                self.palette[name] = curses.color_pair(index)

    @property
    def direction(self):
        return DIRECTIONS[self.column]

    def entry(self, direction):
        entries = self.draft.entries[direction]
        return entries[self.index[direction]] if entries else None

    def add_entry(self):
        self.draft.add(self.direction)
        self.index[self.direction] = len(self.draft.entries[self.direction]) - 1
        return self.entry(self.direction)

    def put(self, y, x, text, style='', width=None):
        height, columns = self.screen.getmaxyx()
        available = columns - x - 1
        if width is not None:
            available = min(available, width)
        if 0 <= y < height and available > 0:
            attribute = self.palette.get(style, self.curses.A_REVERSE if style.endswith('_focus') else 0)
            fitted = _fit(text, available)
            if fitted:
                try:
                    self.screen.addstr(y, x, fitted, attribute)
                except self.curses.error:
                    pass  # A resize can invalidate a cell between measurement and drawing.

    def frame(self, title):
        self.screen.erase()
        height, columns = self.screen.getmaxyx()
        self.put(0, 1, 'HUBE  /  ' + self._(title), 'offer')
        self.put(0, max(1, columns - len(self.name) - 3), self.name, 'need', max(0, columns // 3))
        self.put(1, 1, self.host.context() if self.host else '─' * max(0, columns - 3), 'dim')
        return height, columns

    def draw(self):
        height, width = self.frame('MY PROFILE')
        self.put(2, 1, self._('What can I bring into the world?'))
        self.put(3, 1, self._('Interests') + ' · ' + self._('Capabilities'), 'dim')
        column_width = max(1, (width - 5) // 2)
        visible = min(len(self.keys), max(1, height - 12))
        offset = max(0, self.row - visible + 1)
        for column, direction in enumerate(DIRECTIONS):
            x = 2 + column * (column_width + 1)
            self.put(4, x, self._(COLUMN_LABELS[direction]), direction, column_width)
            for y, key in enumerate(self.keys[offset:offset + visible], 5):
                current = self.entry(direction)
                marked = current is not None and (key in current['categories'] if key else not current['categories'])
                focused = column == self.column and y - 5 + offset == self.row
                label = self._(self.taxonomy.label(key) if key else 'Uncategorised')
                style = direction + '_focus' if focused else direction if marked else 'dim'
                self.put(y, x, ('● ' if marked else '○ ') + label, style, column_width)
        y = 5 + visible
        self.put(y, 1, '─' * max(0, width - 3), 'dim')
        entry = self.entry(self.direction)
        count = len(self.draft.entries[self.direction])
        focused_key = self.keys[self.row]
        category = self._(self.taxonomy.label(focused_key) if focused_key else 'Uncategorised')
        label = self._(COLUMN_LABELS[self.direction]) + '  /  ' + category
        if count:
            label += f'  ·  {self.index[self.direction] + 1} / {count}'
        self.put(y + 1, 1, label + ' · ' + self._(self.draft.state(entry)), self.direction)
        self.put(y + 2, 1, (entry and entry['description']) or self._('No description yet'))
        self.put(y + 3, 1, self.notice or self._('Enter Edit · Space Toggle · Tab Switch · + Add · [ ] Entries · - Remove'), 'dim')
        self.put(y + 4, 1, self._('i Interests · c Capabilities · s Review & share · Esc/b Back · ? Help'), 'dim')
        if self.assistant:
            self.put(y + 5, 1, self._('a Suggest tags'), 'dim')
        self.screen.refresh()

    def read(self):
        return self.screen.get_wch()

    def edit_text(self, label, value):
        start = value
        cursor = len(value)
        while True:
            height, width = self.frame(label)
            before_cursor = sum(_width(char) for char in value[:cursor])
            tail = 0
            while tail < cursor and before_cursor > max(0, width - 5):
                before_cursor -= _width(value[tail])
                tail += 1
            visible = value[tail:]
            self.put(3, 1, visible, self.direction + '_focus')
            self.put(5, 1, self._('Enter Keep draft · Esc Back · F1 Help · {count}/{limit}').format(
                count=len(value), limit=MAX_DESCRIPTION), 'dim')
            if height > 3 and width > 2:
                cursor_x = 1 + sum(_width(char) for char in value[tail:cursor])
                self.screen.move(3, min(width - 2, cursor_x))
            self.screen.refresh()
            key = self.read()
            if key in ('\n', '\r', self.curses.KEY_ENTER):
                return value
            if key == '\x1b':
                return start
            if key == self.curses.KEY_F1 and self.host:
                self.host.help([self._('Your draft will be here when you return.')])
            if key in (self.curses.KEY_BACKSPACE, '\x7f', '\b') and cursor:
                value = value[:cursor - 1] + value[cursor:]
                cursor -= 1
            elif key == self.curses.KEY_DC:
                value = value[:cursor] + value[cursor + 1:]
            elif key == self.curses.KEY_LEFT:
                cursor = max(0, cursor - 1)
            elif key == self.curses.KEY_RIGHT:
                cursor = min(len(value), cursor + 1)
            elif key == self.curses.KEY_HOME:
                cursor = 0
            elif key == self.curses.KEY_END:
                cursor = len(value)
            elif isinstance(key, str) and key.isprintable() and len(value) < MAX_DESCRIPTION:
                value = value[:cursor] + key + value[cursor:]
                cursor += 1

    def review(self):
        changes, details = self.draft.changes()
        if not changes and not details:
            self.notice = self._('No profile changes to share.')
            return None
        lines = []
        for change in changes:
            withdrawn = change['status'] == 'withdrawn'
            row = self.draft.original[change['id']] if withdrawn else change
            categories = ', '.join(self._(self.taxonomy.label(key)) for key in row['categories'])
            label = self._('Withdraw') + ' · ' if withdrawn else ''
            lines.append((label + self._(COLUMN_LABELS[row['direction']]) + ' · ' +
                          (categories or self._('Uncategorised')), row['direction']))
            lines.append(('  ' + row['description'], ''))
        for field, value in details.items():
            lines.append((self._(DETAIL_LABELS[field]) + ' · ' + (value or self._('Clear field')), ''))
        offset = 0
        while True:
            height, width = self.frame('REVIEW SHARED PROFILE')
            self.put(2, 1, self._('Previously shared details remain in the event log.'), 'dim')
            # Wrap descriptions in review so the full submitted text can be inspected.
            wrapped = []
            columns = max(1, width - 3)
            for line, style in lines:
                while line:
                    piece = _fit(line, columns) or line[:1]
                    wrapped.append((piece, style))
                    line = line[len(piece):]
            capacity = max(1, height - 6)
            offset = min(offset, max(0, len(wrapped) - capacity))
            for y, (line, style) in enumerate(wrapped[offset:offset + capacity], 4):
                self.put(y, 1, line, style)
            at_end = offset + capacity >= len(wrapped)
            controls = ('Enter Share profile · ↑↓ Review · Esc/b Back' if at_end
                        else '↓ Read remaining changes · Esc/b Back')
            self.put(height - 1, 1, self._(controls), 'dim')
            self.screen.refresh()
            key = self.read()
            if key in ('y', '\n', '\r', self.curses.KEY_ENTER) and at_end:
                return {'kind': 'edit_declarations', 'changes': changes, 'details': details}
            if key in ('\x1b', 'b'):
                return None
            if key == self.curses.KEY_UP:
                offset = max(0, offset - 1)
            if key == self.curses.KEY_DOWN:
                offset += 1

    def propose_categories(self, entry):
        self.frame('SUGGESTED CATEGORIES')
        self.put(2, 1, self._('Send this draft description to the optional assistant?'))
        self.put(3, 1, self._('y Continue · Esc Back'), 'dim')
        self.screen.refresh()
        if self.read() != 'y':
            return
        allowed = self.taxonomy.keys
        categories = suggested_keys(self.assistant, 'categories', {
            'description': entry['description'], 'direction': self.direction,
            'categories': dict(self.taxonomy.categories),
        }, allowed)
        if not categories:
            self.notice = self._('No category suggestions.')
            return
        offset = 0
        while True:
            height, _ = self.frame('SUGGESTED CATEGORIES')
            limit = max(1, height - 4)
            offset = min(offset, max(0, len(categories) - limit))
            for y, key in enumerate(categories[offset:offset + limit], 3):
                self.put(y, 1, self._(self.taxonomy.label(key)), self.direction)
            self.put(2, 1, self._('y Add to draft · ↑ ↓ Review · Esc Back'))
            self.screen.refresh()
            key = self.read()
            if key == 'y' and offset + limit >= len(categories):
                entry['categories'] = list(dict.fromkeys(entry['categories'] + categories))
                return
            if key == self.curses.KEY_DOWN:
                offset += 1
            elif key == self.curses.KEY_UP:
                offset = max(0, offset - 1)
            elif key == '\x1b':
                return

    def run(self):
        while True:
            self.draw()
            key = self.read()
            self.notice = ''
            entry = self.entry(self.direction)
            category = self.keys[self.row]
            if key in ('\x1b', 'b'):
                return None
            if key == '?' and self.host:
                self.host.help([
                    self._('↑↓ Navigate · Tab Switch column · Space Select · Enter Edit description'),
                    self._('+ Add · [ ] Browse entries · - Remove · i Interests · c Capabilities'),
                    self._('s Review & share · Esc/b Discard draft'),
                ])
            elif key == self.curses.KEY_UP:
                self.row = (self.row - 1) % len(self.keys)
            elif key == self.curses.KEY_DOWN:
                self.row = (self.row + 1) % len(self.keys)
            elif key in ('\t', self.curses.KEY_LEFT, self.curses.KEY_RIGHT, self.curses.KEY_BTAB):
                self.column = 1 - self.column
            elif key in ('+', '\n', '\r', self.curses.KEY_ENTER):
                if entry is None or key == '+':
                    entry = self.add_entry()
                entry['description'] = self.edit_text(COLUMN_LABELS[self.direction], entry['description'])
            elif key == ' ':
                self.toggle_category(entry, category)
            elif key in ('[', ']') and entry:
                count = len(self.draft.entries[self.direction])
                self.index[self.direction] = (self.index[self.direction] + (1 if key == ']' else -1)) % count
            elif key == '-' and entry:
                entries = self.draft.entries[self.direction]
                entries.pop(self.index[self.direction])
                self.index[self.direction] = max(0, min(self.index[self.direction], len(entries) - 1))
            elif key in ('i', 'c'):
                field = 'interests' if key == 'i' else 'capabilities'
                self.draft.details[field] = self.edit_text(DETAIL_LABELS[field], self.draft.details[field])
            elif key == 'a' and self.assistant and entry and entry['description'].strip():
                self.propose_categories(entry)
            elif key == 's':
                command = self.review_or_focus()
                if command:
                    return command

    def toggle_category(self, entry, category):
        if entry is None:
            entry = self.add_entry()
        categories = entry['categories']
        if category is None:
            categories.clear()
        elif category in categories:
            categories.remove(category)
        elif category in self.taxonomy.keys or category in self.draft.original.get(
                entry.get('id'), {}).get('categories', ()):
            categories.append(category)

    def review_or_focus(self):
        incomplete = self.draft.incomplete()
        if incomplete is None:
            return self.review()
        direction, index = incomplete
        self.column = DIRECTIONS.index(direction)
        self.index[direction] = index
        self.notice = self._('Entry {number} needs a description. Press Enter to edit.').format(number=index + 1)
        return None


def profile_palette(viewport):
    return {
        'offer': viewport.colour_style('#a3e8c7'),
        'need': viewport.colour_style('#c4a7e7'),
        'dim': viewport.colour_style('#a6a6a6'),
        'offer_focus': viewport.curses.A_REVERSE | viewport.colour_style('#a3e8c7'),
        'need_focus': viewport.curses.A_REVERSE | viewport.colour_style('#c4a7e7'),
    }


def draft_on_screen(host, declarations, details, taxonomy, name, assistant=None):
    viewport = host.viewport
    return ProfileScreen(viewport.window, viewport.curses, ProfileDraft(declarations, details),
                         taxonomy, name, host._, assistant, host=host).run()


def edit_profile(declarations, details, taxonomy, name, translate, assistant=None):
    import curses

    draft = ProfileDraft(declarations, details)
    previous = locale.setlocale(locale.LC_CTYPE)
    try:
        if locale.getencoding().lower() != 'utf-8':
            for candidate in ('C.UTF-8', 'en_US.UTF-8'):
                try:
                    locale.setlocale(locale.LC_CTYPE, candidate)
                except locale.Error:
                    continue
                else:
                    break
        return curses.wrapper(lambda screen: ProfileScreen(
            screen, curses, draft, taxonomy, name, translate, assistant).run())
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)
