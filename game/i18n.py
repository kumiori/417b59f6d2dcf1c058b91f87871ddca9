import gettext
from pathlib import Path


def translator(locale='en'):
    if locale not in {'en', 'it'}:
        raise ValueError('unsupported_locale')
    return gettext.translation('game', localedir=Path(__file__).parent / 'locales',
                               languages=[locale], fallback=locale == 'en').gettext
