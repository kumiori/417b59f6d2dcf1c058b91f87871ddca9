# Hube — terminal MVP 0.1

Help organise a presentation of **Non ho mai imparato**. The fictional
**HUBE / STOP 01** starts with **2/6** conditions verified. Secure the four
missing conditions through offers, commitments and independent verification.

## Play

Python 3.11 or newer. The runtime depends on the standalone Game-Gamer core,
with its TUI extra for Unicode-aware terminal display. Install this project before playing:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-deps --require-hashes -r requirements/game-gamer-release.txt
.venv/bin/python -m pip install -e .
. .venv/bin/activate
```

Game-Gamer is installed from the checksum-locked wheel bundled in `vendor/`.
`config/game-gamer-release.json` records its exact version and immutable source.
A sibling Commons checkout and a PyPI release of the core are not needed.
Future upgrades arrive as review-only PRs; see [release propagation](docs/GAMER_RELEASES.md).

```sh
.venv/bin/game play
```

The interactive client opens in a full-screen terminal. Choose **Explore the
world** to inspect the book and its surroundings. **Act** opens the seeded
STOP 01 conditions, separate presentation proposals, and contextual requests.
Use **People** to browse profiles, **My contributions** to inspect or amend
your own work, and **Journey** to see the recorded history.

Use arrows and Enter to navigate, Esc or `b` to return, and `?` for help.
Press `0` on the main menu to exit. Piped input and `--line` use the
line-based client. See the [gameplay and terminal guide](docs/GAMEPLAY_UX.md)
for clean saves, disposable simulations and local invitations.
The default save is `.hube.sqlite`. For a separate game or Italian interface,
put global options before `play`:

```sh
.venv/bin/game --db .hube.sqlite.stop01 --locale it play
```

Choose Marco, Andres, Editor or Player X, or join with an alias. When you edit
your shared profile in **My Contributions → Edit shared profile**, use **↑/↓**
to browse categories, **Tab** to switch between **I Offer** and **I Seek**, and
**Space** to toggle categories for the selected entry. Press **Enter** to edit
its description, **+** to add another entry, **[ / ]** to cycle entries, and
**−** to remove one. Entries may stay uncategorized. Press **s** to review and
**y** to confirm. **Esc** backs out of review or discards the editor draft.
Previously shared details remain in the event log after editing or withdrawing.

**Potential Connections** shows who offers categories that others seek.
Select a pair to see the original declarations and available actions.
Use **Act** to record an actionable offer or need. Game actions establish
resource quantities, commitments and verified conditions.
The `ecosystem` CLI command exports the projections.
[Structured profile and taxonomy reference](docs/DECLARATIONS.md)

For solo play or a shared terminal, enable actor switching:

```sh
.venv/bin/game play --hot-seat
```

`[s]` then switches identity. A local identity choice is not authentication.
Use `game play hube-stop-01` for the original menu and `start` / `resume` for
the scripted development client. See [runtime architecture](docs/GAMER_MIGRATION.md).

The game runs with deterministic suggestions. An optional `MissionProposer`
can rank validated candidates by ID using the shared world and the selected
player's declared profile. Players still choose and submit actions through the
same forms.

## Reproduce the complete game

```sh
python3 tools/play_scenario.py
python3 tools/play_scenario.py --locale it
```

These play a semantic presentation of the same canonical simulation, without creating
or modifying a saved game. The original full stdin/stdout acceptance test remains.
To retain an interactive-client run for inspection:

```sh
python3 -m game --db /tmp/hube-demo.sqlite start hube-stop-01 < tests/scenarios/hube_stop_01.stdin
python3 -m game --db /tmp/hube-demo.sqlite timeline
python3 -m game --db /tmp/hube-demo.sqlite network --at 004
python3 -m game --db /tmp/hube-demo.sqlite network --at T4
python3 -m game --db /tmp/hube-demo.sqlite network --time 2026-10-06T00:00:03+00:00
python3 -m game --db /tmp/hube-demo.sqlite people
python3 -m game --db /tmp/hube-demo.sqlite resources
python3 -m game --db /tmp/hube-demo.sqlite requirements
python3 -m game --db /tmp/hube-demo.sqlite log
python3 -m game --db /tmp/hube-demo.sqlite replay
```

`tests/scenarios/hube_stop_01.yaml` contains the fixture reference, structured
commands, literal acceptance expectations and stdin script. It uses JSON syntax,
a YAML subset, to keep the runtime dependency-free. `hube_stop_01.expected.json`
is the checked-in full canonical final state. The terminal outputs are retained
in `tests/transcripts/hube_stop_01.txt` and `hube_stop_01.it.txt`.

## Frozen scenario and explicit decisions

- Four simulated players: Marco, Andres, Editor and Player X. Giulia is a newly
  observed non-player contact. Player X offers their own capacity; nobody commits
  Giulia on her behalf. Newly discovered contacts are not automatically players.
- Fictional Bologna, proposed **14 November 2026**. The date remains unconfirmed
  until its commitment is verified. Time, location and unit must match exactly;
  an offer's availability must cover the requested interval.
- Six required conditions: Marco, books, venue, date, two beds, documentation.
  Marco and books start satisfied. Andres coordinates and the city is known;
  those seed facts do not add two more checklist conditions. The attachment's
  initial “4/6” is corrected to **2/6**.
- Venue availability requires a concrete place node distinct from the city. The
  scenario discovers **Sala Comune**, then attaches it to the venue offer.
- Documentation means a verified **commitment to document** the future event,
  not proof that documentation of an event that has not happened already exists.
- A different player may propose a match, but only its provider may confirm.
  Verification requires another player and a nonempty evidence reference.
  Self-report is insufficient for these four conditions; organizer confirmation
  requires the seeded organizer. These checks simulate roles, not authentication.
- New personal needs and optional propositions remain possible. They do not
  change the frozen minimum event threshold. Marco's personal bed request remains
  reported in the canonical run; beds allocated to the event are not silently
  counted a second time as fulfilment of his separate request.
- The run ends on feasibility. New commands then fail with `game_over`; exact
  retries still return their previous result. Read-only inspection remains available.
  Real commitments changing after the ending belong to a future lifecycle.

These are implementation defaults for the ambiguities in the attachment, not
claims about real people, availability, venues or confirmations. No authored model
or schema document was changed.

## Core API and boundaries

```python
from game import load_fixture, Game

game = load_fixture('hube-stop-01')
world = game.get_world()                    # detached copy
errors = game.validate(command)             # pure validation
result = game.submit(command)               # all-or-nothing in-memory transaction
result = game.apply(command)                # same validated boundary; no bypass
possibilities = game.derive_possibilities() # read-only, disposable matches
requirements = game.evaluate_requirements() # read-only evaluation
result = game.verify(subject, actor='person_003', key='unique-key',
                     evidence_kind='player_confirmation', reference='Evidence note')
network = game.project('network', at=4)
history = game.world_at(event=4)             # transaction 4, inclusive
history = game.world_at(time='2026-10-06T00:00:03+00:00')
game.save('run.sqlite')
restored = Game.load('run.sqlite')           # rebuild from log, no snapshot needed
assert restored.replay().get_world() == restored.get_world()
```

See the scenario for concrete command payloads. Every command has `key`, `kind`
and `actor`. Accepted keys are idempotent across restart; reusing a key with a
different payload fails. Unsupported fields fail rather than being silently ignored.

The six canonical record classes follow the implemented subset of `SCHEMA.md`.
Relations keep node-to-node endpoints: a `satisfies` relation connects the provider
to the resource, and its attributes reference the offer, demand and original action.
Requirements cite supporting verified relation IDs. Feasibility lives in event
metadata, separate from the schema's node lifecycle status. Claim is deferred.

Each log entry is an **atomic transaction** containing every canonical Mutation
with before/after values, action provenance and a deterministic timestamp. Individual
mutation IDs remain inspectable. Transaction 1 initializes the world; transaction 20
records the final verification, requirement change and `event.feasible` together.
Historical queries never expose a half-applied action. Timestamps are logical clock
ticks (one second per transaction from the fixture epoch), not actual wall-clock
confirmation times. Event availability dates are separate domain data.

SQLite appends the complete transaction under a database transaction; no canonical
snapshot is stored. A stale writer fails rather than replacing another run's history.
Replay checks sequence order and mutation before-images. It is not a signed audit
trail and does not make arbitrary edited log files trustworthy.

Possibilities are derived from exact resource IDs, quantity, unit, date and city.
Queries never write history. Proposed, committed and verified allocations reserve
capacity; only verified allocations count toward requirements. Partial capacity
stays visible. Before the ending, withdrawing an offer removes its allocations and
re-evaluates requirements. No unit conversions or inferred equivalences are used.

This is a local **shared simulation**, with campaign-visible data only. Private
visibility fields are rejected; authentication and differentiated visibility policy
are not implemented. Do not use this prototype for private participant data.
The API is not a network service. No AI, map, payment, notifications or multi-stop
campaign mechanics are included.

## Validation and localization

```sh
python3 -m pip install pytest  # in your development environment, if needed
python3 -m pytest -q
python3 tools/compile_catalog.py
```

Tests cover engine mutations, replay, historical views, quantity/compatibility,
provider consent, independent verification, withdrawals, idempotency, persistence
conflicts, the complete real CLI, resume, and identical canonical worlds in English
and Italian. Tests use the public engine API and terminal stdin/stdout boundaries.

Player-facing terminal vocabulary goes through GNU gettext catalogs. Source `.po`
and compiled `.mo` files are included; the small compiler supports this MVP's
single-line singular entries. Canonical IDs, raw JSON/debug projections, and
player-authored names or evidence remain untranslated.

## Paced terminal replay

```sh
python3 -m game simulate hube-stop-01 --paced
python3 tools/play_scenario.py                 # instant by default
python3 tools/play_scenario.py --paced
python3 tools/play_scenario.py --paced --speed 0.5
python3 tools/play_scenario.py --paced --speed 2
python3 tools/play_scenario.py --step
python3 tools/play_scenario.py --instant
```

With the package installed, `game simulate hube-stop-01 --paced` is equivalent.
Use `python3 tools/play_scenario.py --locale it --paced` for Italian.

In iTerm2 or another POSIX terminal:

| Key | Effect |
| --- | --- |
| SPACE | Pause / continue |
| → or + | Double speed |
| ← or - | Halve speed |
| ENTER | Reveal the next semantic beat while paused; stay paused |
| q | Quit presentation |

Step mode begins paused after revealing the initial state. SPACE can resume timed
play. Terminal settings are restored on completion, quit, interruption or error.
Paced output redirected to a file still honours timing but has no keyboard controls
or status escapes. Step mode requires a terminal and fails promptly without one.
Use `--instant` for tests and pipes. Invalid/non-finite speeds and conflicting modes
are rejected. Keyboard speed changes are bounded between ×0.125 and ×64.

`game/replay.py` is the presentation driver; `game/replay_input.py` owns TTY input.
The packaged scenario is mirrored from the acceptance scenario, with a test guarding
against drift. The engine finishes the deterministic run before display begins.
Presentation events derive from accepted actions, mutations, threshold transitions
and freshly appearing possibilities, never from authored claims of success.
Each carries its originating transaction number and simulation timestamp.

The default trajectory has 51 semantic beats and 77.0 seconds of base display holds:

| Beat | Base hold |
| --- | ---: |
| Initial / ordinary | 0.5 s |
| Player statement | 2.5 s |
| Mutation / graph relation | 0.5 s |
| New possibility | 1.5 s |
| Verified threshold | 2.0 s |
| Ending | 3.0 s |

The hold follows the revealed beat. Display duration is base hold divided by current
speed; speed changes take effect during the current hold. Pausing does not consume
its remaining hold. No timing or keyboard state enters the canonical log.

Three times remain distinct:

- **World time:** semantic availability and the proposed event date in canonical
  relation attributes (14 November 2026 in this fixture).
- **Simulation time:** transaction sequence and the fixture's logical `occurred_at`
  timestamps. These existing timestamps are not actual real-world submission times.
- **Display time:** monotonic-clock holds, pause and speed, exclusively in the client.

Quitting a replay stops showing an already simulated trajectory; it neither rewinds
nor partially commits a saved world. All modes produce the same canonical final
world. English semantic output is saved in `tests/transcripts/hube_stop_01.replay.txt`;
the earlier terminal-client transcripts remain intact.

## Inhabit one node

Unresolved minimum conditions are the principal menu: choose Accommodation, then
provide capacity, ask someone, record a contact, connect an offer, confirm your own
commitment or verify another player's commitment. The form binds the canonical
required resource automatically. It shows offered, committed and verified quantities
separately; only verified capacity is secured.

Offers collect quantity/unit, location and availability dates. A concrete place or
object is optional for accommodation; venue offers require a concrete place distinct
from their location. New places are created atomically only when the form completes.

`Add something` retains observations, offers, optional needs, proposals, corrections,
introductions and withdrawals. Funding of 3000 eur can be a discovered need without
becoming a seventh ending condition. `[r]` opens requests, `[0]` saves/exits, and `[s]`
is present only with `--hot-seat`. Inside forms, `b` returns one field, `0` cancels,
and `?` explains the controls. Invalid input repeats the current field. Cancelling an
unfinished form creates nothing; it does not undo earlier completed transactions.

Resource labels are resolved ignoring case and repeated whitespace. Matching names
prompt reuse or an explicit declaration of a different resource. Existing duplicates
remain in history and selectors distinguish the resource required by the event.
Observation categories and typed relation signatures prevent edges such as a person
“knowing” a resource. Sharing an observation never silently becomes an offer.

Possible moves show grounded matches first. Asking people to discover unreported
capacity is explicit exploration scoped to a selected need:

```python
session.possible_moves(demand_id='rel_007', explore=True)
game.project_need('rel_007')  # offered / committed / verified capacity
```

The runnable input for the Funding and two-provider accommodation traversal is
`tests/scenarios/funding_two_beds.stdin`; its terminal output is
`tests/transcripts/funding_two_beds.txt`. The older `start` / `resume` commands remain
development terminals; this guided navigation belongs to `play`.

A request is a canonical `requested` relation from its author to the recipient,
with an explicit demand ID. It does not reserve capacity or satisfy a requirement.
Only that recipient may accept, decline or modify it. Acceptance creates a reported
offer; modification creates an offer on revised terms. Neither confirms an event
commitment. Connection → provider confirmation → independent verification still
follows. Declining adds no capacity. Requests can wait for a discovered contact to
join the world. The inbox is derived from those pending relations.

Possible requests mean “ask whether this person can help,” never an inference that
they possess an unreported capacity. A recorded social context may accompany a
request, with the actual source of that observation shown. Third-party observations
such as “Marco knows Giulia” remain reports by the acting player. Explicit reported
introductions are separate actions; a `knows` edge is never counted as an introduction.

Corrections supersede the acting player's own unverified social observations with
a new reported relation and a reason. The original remains in history as withdrawn.
Seeded verified facts and other people's reports are not editable through this flow.

`PlayerSession(game, actor)` is the actor-bound command boundary. Its `submit`
rejects another actor and its `switch` requires `hot_seat=True`. The raw `Game` API
remains the trusted simulation / development boundary. This is local shared-file
play, not a live network multiplayer service. Reopen `play` to read another session's
saved changes; a concurrent save conflict exits without overwriting their log.

## The ending: causal recap

After the ending, interactive play and completed terminal replays ask:

```text
See how we got here? [y/N]
```

The recap is optional and read-only. Declining or reaching EOF leaves the world
unchanged. Replay controls are restored to ordinary input before this question.
For scripted output, request it explicitly:

```sh
python3 tools/play_scenario.py --instant --recap
python3 -m game simulate hube-stop-01 --paced --no-recap
python3 -m game journey
python3 -m game journey --json
python3 -m game journey --at 4
```

The two equivalent core projections are:

```python
game.project_journey('event_001')
game.project_causal_trace(target='event_001', terminal_state='feasible')
```

`game/journey.py` follows each required condition's current verified supports back
to its offer, any explicitly linked request/social context, connection, provider
confirmation and verification evidence. Used venue or provider discoveries carry
their originating action. Seed facts are identified as already verified. Unverified
or withdrawn allocations cannot enter a successful support path. Historical calls
show the support actually present at that time, without borrowing later knowledge.

This is a trace of recorded dependencies, not an invented social story or a proof
of counterfactual necessity. Incidental observations are not attached to a winning
path merely because they occurred earlier. For example, the original simulation's
Giulia observation is excluded from its winning paths; its beds came from Player X.
When a request explicitly uses Marco's reported connection to Giulia and her response
supplies the verified beds, that different play history yields that causal path.

The terminal recap leads with the branching trace and record / transaction IDs,
then requirement paths, causal versus total actor activity, and before/after counts.
Counts use their actual definitions: active offers, fulfilled personal needs,
verified allocations, explicitly reported introductions, and new resource types.
Shared seed books are not fabricated as two offers; a personal need is not silently
satisfied by beds allocated to the event. The recap says **feasible**, not that the
real-world event has already happened.

Reference outputs: `tests/transcripts/hube_stop_01.journey.txt` (the simulation's
causal recap) and `tests/transcripts/hube_stop_01.play.txt` (a full hot-seat play
session with its optional recap). The core seed and canonical simulation remain
unchanged. The test suite also covers a Giulia request/response/verification path.

## Reconstructed graffiti splash

The optional `hube_tag` package reconstructs timed drawing gestures from video and
plays them in ASCII, Unicode line art, or Braille. Playback uses only the standard
library; offline processing uses the `vision` extra and FFprobe.

```sh
python3 -m hube_tag play output/tag/trajectories.json --renderer braille --duration 8
python3 -m game play --splash output/tag/trajectories.json
```

These commands use a local reconstruction at `output/tag/trajectories.json`. See
the [pipeline documentation](docs/TAG_PIPELINE.md) to generate one and the
[measured evaluation](docs/TAG_EVALUATION.md) for the original experiment.
