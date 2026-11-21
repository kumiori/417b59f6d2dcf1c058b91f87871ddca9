"""POSIX terminal controls (iTerm2 and ordinary TTYs); always restore settings."""
import os
import select
import sys


class Keyboard:
    def __init__(self, enabled=True):
        self.interactive = enabled and sys.stdin.isatty() and os.name == 'posix'
        self.saved = None

    def __enter__(self):
        if self.interactive:
            import termios
            import tty
            self.fd = sys.stdin.fileno()
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def read(self, timeout):
        if not select.select([self.fd], [], [], timeout)[0]:
            return None
        data = os.read(self.fd, 1)
        if not data:
            return 'q'
        if data == b'\x1b':
            # Arrow sequences can arrive in separate reads.
            for _ in range(2):
                if select.select([self.fd], [], [], .03)[0]:
                    data += os.read(self.fd, 1)
                else:
                    break
        return data.decode('ascii', errors='ignore')

    def __exit__(self, *exc):
        if self.saved is not None:
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
