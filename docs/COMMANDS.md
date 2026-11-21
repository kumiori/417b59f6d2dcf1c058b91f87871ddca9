# Hube command architecture

## From input to history

1. The terminal collects input. `PlayerSession.submit` binds the player to the
   command. Scripts and the legacy client can call `Game.submit` directly.
2. The pinned Game-Gamer runtime holds the transaction lock. Hube looks up the
   command in `game/command_contracts.py`, checks its envelope and accepted
   fields, and resolves typed retries before checking actor eligibility and
   whether the game has ended.
3. A handler in `game/commands.py` checks its required values, actor authority
   and domain rules. It writes a candidate world and action using
   `CommandPlan`. Shared capacity rules live in `game/capacity.py`; actor and
   request policies live in `game/policies.py`. An error discards the plan.
4. `Game._prepare` records the planned action, re-evaluates requirements and
   marks the ending when the six required conditions are satisfied. Game-Gamer
   records the mutations together. The CLI saves via the shared SQLite API.
5. Replay applies recorded mutations. `game/projections.py` derives detached
   views from current or historical state. The reusable declaration code in
   `game_gamer_semantics/` applies semantic revisions and explicit ordering.

Hube owns its payloads, authority rules and game policies. Transaction history,
locking, replay and persistence belong to Game-Gamer. Exact retry comparison
is generic in principle. Hube calls it locally because the pinned runtime
delegates retry payload validation to its host.

## Adding a command

- Specify the allowed and required payload fields, authorised actors, domain
  preconditions, failure identifiers and the event or action the command
  records. Check existing handlers and policies first.
- Register one `CommandSpec` in `game/command_contracts.py`. Handlers read the
  candidate supplied by `CommandPlan` and return an event summary. Use the
  plan's node and relation constructors to preserve IDs and provenance. The
  current relation constructor allocates one new relation ID per transaction.
- Submit through the usual game or player interface. Test success, rejection,
  unchanged state and history on rejection, retries and replay. Add a terminal
  form only when the command needs an interactive entry point.

### Worked example using the existing introduction command

The registry maps `introduce` to `commands.introduce` with payload fields
`source_id` and `target_id`. Both fields are required when the handler reads
them. The handler rejects a self-introduction or a non-person endpoint. On
success, it adds one `introduced` relation, identifies the relation and the
two people as action targets, and returns `introduction.reported`.

```python
from game import load_fixture
from game.player import PlayerSession

game = load_fixture()
session = PlayerSession(game, 'person_003')
command = {
    'kind': 'introduce', 'key': 'intro-1',
    'source_id': 'person_001', 'target_id': 'person_002',
}
accepted = session.submit(command)
assert accepted['ok']
assert session.submit(command) == accepted
before = game.get_world(), game.project('log')
invalid = {**command, 'key': 'intro-2', 'target_id': 'person_001'}
assert session.submit(invalid)['errors'] == ['invalid_introduction']
assert (game.get_world(), game.project('log')) == before
assert game.replay().get_world() == game.get_world()
```

## Complexity gate

Install the pinned analyser with `python -m pip install -e '.[quality]'` and
run `python tools/check_complexity.py` with the environment on `PATH`.
The check covers the production packages and tools. The AST measures physical
line spans and nested conditionals and loops, with `elif` at the same level as
`if`. Ruff measures cyclomatic complexity. `--report` prints the full results
and `--exceptions` prints entries above a threshold. Use `--root` to compare
with another checkout or an archive of commit `020942b`.

| Metric | Review threshold | Reviewed baseline | Refactored |
| --- | ---: | ---: | ---: |
| `Game._prepare` lines | 50 | 277 | 11 |
| `Game._prepare` cyclomatic complexity | 15 | 77 | 2 |
| `Game._prepare` conditional depth | 3 | 4 | 1 |
| `Game` class lines | 300 | 553 | 109 |
| `game/engine.py` lines | 500 | 576 | 139 |
| Repository-wide threshold breaches | | 53 | 44 |

The longest new handler is 38 lines. The maximum handler complexity is 8 and
maximum conditional depth is 2. The gate caps each remaining exception at its
recorded value in [the baseline](complexity-baseline.json). Document the reason
for any new exception before updating that file. The refactor added zero new
or worsened exceptions.

## Remaining architectural debt

- The pinned transaction API validates by planning and plans again to commit.
  Unifying the two calls requires a Game-Gamer interface change and compatibility
  checks across hosts.
- Legacy profile reconstruction still scans action history. The declaration
  revision planner remains over the function-length threshold. Both paths
  need to preserve the identity and provenance of records from old saves.
- The exception baseline lists terminal dispatch and forms, causal replay and
  rendering, and TAG video stages. They remain part of the gate and were outside
  this command remediation. Existing Ruff formatting and lint debt is tracked
  separately from these complexity thresholds.
