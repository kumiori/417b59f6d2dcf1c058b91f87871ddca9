"""Compile our single-line, singular gettext catalog (no external tooling needed).

Run: python tools/compile_catalog.py
This MVP uses no plural entries or contexts. Fail explicitly if either appears.
"""
import ast
from pathlib import Path
import struct


def compile_catalog(source):
    messages = {}
    msgid = None
    for line in source.read_text().splitlines():
        if line.startswith('msgid '):
            msgid = ast.literal_eval(line[6:])
        elif line.startswith('msgstr '):
            messages[msgid] = ast.literal_eval(line[7:])
        elif line and not line.startswith('#'):
            raise ValueError('Only single-line singular catalog entries are supported')
    pairs = sorted((key.encode(), value.encode()) for key, value in messages.items())
    n = len(pairs)
    offset = 28 + 16*n
    originals, translations, data = [], [], b''
    for key, _ in pairs:
        originals.append((len(key), offset + len(data)))
        data += key + b'\0'
    for _, value in pairs:
        translations.append((len(value), offset + len(data)))
        data += value + b'\0'
    header = struct.pack('<7I', 0x950412de, 0, n, 28, 28+8*n, 0, 0)
    tables = b''.join(struct.pack('<2I', *row) for row in originals + translations)
    source.with_suffix('.mo').write_bytes(header + tables + data)


if __name__ == '__main__':
    for source in (Path(__file__).resolve().parents[1] / 'game/locales').glob('*/LC_MESSAGES/game.po'):
        compile_catalog(source)
