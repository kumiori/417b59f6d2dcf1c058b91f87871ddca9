# Hube engineering constitution

This is the repository-wide engineering standard for human and agent contributors. Apply it to design, implementation and review. Keep [the world model](GAME_MODEL.md), [schema](SCHEMA.md), and [implemented contracts](README.md) in view. The README and canonical scenario spell out the implemented STOP 01 subset. If a proposed change would alter an established contract, identify the change and its rationale explicitly.

## Engineering objective

Produce correct, understandable, minimally complicated, documented software that a human developer can maintain independently. Review responsibility, dependency direction, and the ease of tracing a change as well as the test results. Give each module a clear responsibility and each domain rule one authoritative implementation. Prefer composition where the relationship is delegation or reuse. Add abstractions only when their concrete benefit is clear.

## Architecture and authority

| Component | Responsibility and dependency direction |
| --- | --- |
| `game/_shared.py` and the pinned `game-gamer` package | Hube's import boundary to the standalone runtime. Game-Gamer owns the in-memory transaction, mutation history, replay, and append-only SQLite log. Keep Hube vocabulary, fixtures and governance in Hube. See [the runtime migration](docs/GAMER_MIGRATION.md). |
| `game/engine.py`, `game/command_contracts.py`, and `game/commands.py` | `Game` supplies the domain hooks of `WorldEngine`. Command contracts register explicit handlers, which plan changes on detached world state. See [the command architecture and worked example](docs/COMMANDS.md). |
| `game/model.py`, `game/capacity.py`, `game/policies.py`, `game/requirements.py`, and `game/fixtures/` | Own the Hube schema, asset and capacity rules, actor and request policies, requirement evaluation and scenario seed data. Keep those rules callable independently of a terminal. |
| `game/declarations.py` and `game_gamer_semantics/` | Hube binds declarations to actor metadata, loads its taxonomy, and reads legacy profiles. The extension owns reusable taxonomy, revision and projection logic and the semantic assistant adapter. Keep the extension independent of Hube terminal code, fixture IDs and save paths. See [the declarations contract](docs/DECLARATIONS.md). |
| `game/player.py`, `game/play.py`, `game/mission_terminal.py`, `game/profile_editor.py`, and `game/terminal.py` | The player session binds commands to the active actor. Terminal clients collect input, show projections, submit commands, and invoke the shared save API. Preserve the scripted CLI and existing saves when changing the interactive path. |
| `game/tui_*.py` and `game/ecosystem_graph.py` | The full-screen client composes the pinned shared viewport and graph renderer with Hube's read models. Keep route state and drafts local, and route every write through the active player session. [Gameplay and terminal architecture](docs/GAMEPLAY_UX.md) |
| `game/presentations.py`, `game/context_requests.py`, and `game/contribution_commands.py` | Own scoped candidate contributions, local contextual requests and author-controlled amendments. Preserve the seeded scenario's event contract. |
| `game/projections.py`, `game/missions.py`, `game/journey.py`, `game/replay.py`, and `game/recap.py` | Build candidate moves, causal views and presentations from validated state and history. Scenario simulation uses its own world. Display state and optional advice have no authority to write to a player's world. |
| `hube_tag/` | Optional vision pipeline and terminal splash. Keep its dependencies and generated artifacts out of core play and world history. See [the TAG pipeline](docs/TAG_PIPELINE.md). |

Follow the dependencies from the clients to Hube domain code and from Hube to the shared runtime. Before adding machinery, inspect the installed pinned Game-Gamer revision and relevant sibling applications when available. Reuse existing engines, stores, projection logic and renderers where their contracts match. A neighbouring checkout is useful for comparison. Runtime installation and execution rely on the declared dependency.

## Commands and governance

1. A client collects a command with `key`, `kind` and `actor`. Route interactive player commands through `PlayerSession.submit`. The legacy development client submits directly to `Game.submit`. Use `Game.submit` or the equivalent validated `Game.apply` entry point for authoritative writes. Keep fixture initialization and replay on their existing runtime paths.
2. Keep dispatch, input validation, actor authority, lifecycle admissibility and candidate-state transformation distinguishable. For a new command or a command refactor, use explicit handlers and contracts. Use typed interfaces at public boundaries where they clarify accepted values and outcomes. When the command family grows, use a single dispatch registry if it makes the accepted fields and handlers easier to find together.
3. Keep validation side-effect free. Handlers work on candidate state. The runtime commits a successful command as one event with all mutations, action provenance and a deterministic timestamp. The CLI saves through the shared append-only SQLite API. Preserve exact retries, conflicting-key rejection, ordered replay, and stale-writer checks. Rejected commands leave world state and history unchanged.
4. Use named predicates or policies for meaningful conditions and shared queries for recurring rules. Keep malformed input, insufficient authority, inadmissible transitions, accepted no-ops or exact retries, and accepted changes distinguishable through the existing contract. Preserve established error keys and rejection semantics during refactors.
5. In STOP 01, only the provider confirms a commitment. An independent actor verifies it with admissible evidence. Preserve organizer authority, quantity and compatibility checks, and allocation limits. Only verified support counts toward the six required conditions. Feasibility ends the run, while historical inspection and exact retries remain available. Local actor selection is simulated authority.

## State invariants

These invariants apply to Hube and to reusable semantics built on Game-Gamer.

| Invariant | Required behaviour |
| --- | --- |
| Admissibility | Validate domain relationships on every command path before they enter authoritative history. |
| Identity | Only a retry with the same typed command payload may reuse a command key. Compare mapping fields independently of key order and preserve list order and scalar types. |
| Determinism | Equivalent states and configuration produce equivalent ordered projections across persistence and replay. Specify the ordering. |
| Round-trip integrity | Keeping a field during editing preserves the exact valid value. Editor controls have meaning only on explicit input. |
| Semantic revision | Increment a record revision and update its change provenance only when canonical content changes. Distinguish rejected attempts, recorded actions and effective changes. |

## State, provenance and projections

- Keep the event history authoritative. Current state and historical views derive from whole transactions. Queries return detached data and leave the world, log and save untouched. Preserve stable IDs and ordering, replay of older saves, and reproducible results for a given history and configuration.
- Preserve the meaning of unknown, absent, inferred, reported, committed and verified information. Sourced actions and evidence support causal recaps. Shared declaration overlap is a suggestion, while verified game support follows the commitment lifecycle.
- Keep draft edits local until explicit confirmation. Use the subject's current declaration revision, preserve original text and provenance, and retain prior shared history after edits or withdrawal. Keep stable taxonomy keys when extending the vocabulary and version taxonomy changes.
- Assistants may rank or select known candidates using detached context. Filter their outputs against those candidates and keep the deterministic fallback. A player must confirm any game action through the usual governance path.
- Keep canonical identifiers, error keys and record values stable across locales. Localise player-facing text through gettext and compile the catalogue when changing it.

## Complexity review thresholds

| Metric | Target | Review required |
| --- | ---: | ---: |
| Function length | <30 lines | >50 lines |
| Module length | <300 lines | >500 lines |
| Class length | <200 lines | >300 lines |
| Cyclomatic complexity per function | ≤10 | >15 |
| Conditional nesting | ≤2 levels | >3 levels |

Review threshold crossings and existing complexity you increase. Explain any exception by the needs of the implementation and record consequential decisions with their rationale. Extract cohesive responsibilities and simplify the state or rule model. Artificial fragmentation, wrappers that simply forward calls and broad reformatting provide no complexity credit.

## Documentation and tests

- Use names that convey domain meaning and give major modules concise responsibility docstrings. Document public contracts, invariants, assumptions, side effects, and failure conditions. Explain the reason for surprising design choices in comments.
- Update this architecture map or its linked references when component ownership, dependencies, governance, command lifecycle or extension points change. Record important decisions and their rationale in the corresponding architecture or domain document.
- Establish the test baseline before changing behaviour or structure. Add characterisation coverage before refactoring when existing tests leave relevant behaviour unspecified. Preserve acceptance expectations unless an intentional contract change requires new ones.
- Cover each affected rule through its normal entry points. Exercise success, invalid payloads, unauthorised actors, inadmissible transitions, and boundary cases. Check that rejected commands leave state and history unchanged. For relevant changes, test exact retries, replay after save and reload, stale writers, historical projections, and older event or payload formats.
- Use `tests/scenarios/hube_stop_01.yaml` and `tests/scenarios/hube_stop_01.expected.json` for the canonical trajectory. Use temporary databases or copies for tests and manual inspection. Compare the canonical state as well as the presentation when changing play or replay. Preserve English and Italian behaviour and the scripted client where relevant.

## Quality checks

Use the project virtual environment with Python 3.11 or newer. Run `python -m pytest -ra` for the full suite. Install `.[test]` for game tests and `.[vision,test]` plus working `ffmpeg` and `ffprobe` for the full TAG suite. Report skipped or environment-blocked cases with their cause. Run `python tools/compile_catalog.py` when changing gettext sources and verify the localised path.

Install `.[quality]` to use the pinned Ruff version, then run `python tools/check_complexity.py`. The gate checks all five complexity thresholds against [the documented baseline](docs/complexity-baseline.json). Document the reason for any new exception in the relevant design or architecture document before updating the baseline. Formatting and lint warnings in existing code are review inputs. Report introduced warnings or justified exceptions and keep unrelated cleanup out of feature changes.

```sh
ruff format --check --isolated --target-version py311 \
  --config "format.quote-style='single'" game game_gamer_semantics hube_tag tests tools
ruff check --isolated --target-version py311 game game_gamer_semantics hube_tag tests tools
```

Check type consistency at changed public boundaries. When introducing or extending automated quality checks, keep the tool versions, scope, and commands reproducible. Include formatting, lint, complexity, public-boundary type checks and regression coverage. Base any enforced checks on an inspected baseline.

## Delivery

Before implementation, inspect the affected architecture and reusable components, establish the relevant test baseline, and describe the intended change and principal risks. After implementation, report the exact changes, architectural decisions, tests and quality checks, remaining limitations, any added dependencies or abstractions, and any intentional behaviour changes. Preserve unrelated work already in the checkout.
