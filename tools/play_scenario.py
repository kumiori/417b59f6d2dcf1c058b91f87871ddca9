"""Play the canonical scenario through the semantic terminal replay client."""
from pathlib import Path
import sys

# Permit running from an uninstalled checkout without changing working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.terminal import main

if __name__ == '__main__':
    # Keep the existing --locale spelling while routing to the same game CLI.
    import argparse
    from game.replay import add_replay_arguments
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--locale', choices=['en', 'it'], default='en')
    add_replay_arguments(parser)
    args = parser.parse_args()
    raise SystemExit(main(['--locale', args.locale, 'simulate', 'hube-stop-01',
                          '--' + args.mode, '--speed', str(args.speed)] +
                         (['--recap'] if args.recap is True else ['--no-recap'] if args.recap is False else [])))
