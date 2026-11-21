# HUBE runtime migration

The frozen HUBE commit `52fbfe1` used `commons-game>=0.1.0` for transaction
handling, event records and SQLite persistence. It also fell back to importing
`commons_engine` from a neighbouring Commons checkout. The Phase 0 baseline
used the original Commons engine at checkpoint `f082967d47c87e97f4a62dbe7536b6f3743c097b`.

HUBE now imports `WorldEngine`, `Mutation`, `load_log` and `save_log` from the
standalone Game-Gamer 0.2.0 package through `game/_shared.py`, a boundary that
only re-exports the four imports. The dependency is pinned to
`439473d6ee94e59d7c0c29ba16ccbbc915c8fb97` in `pyproject.toml`.

- **GAMER** owns atomic transactions, mutation records, history and SQLite
  persistence.
- **HUBE** owns the STOP 01 world, validation and governance for its domain,
  resource matching, requirement evaluation, causal projections and the terminal.

The fixture, scenario, transaction format and public CLI are preserved. Phase 0
verified that both runtimes completed the fixture and produced byte-identical
world, replay and journey JSON. The standalone runtime also replayed a SQLite
save written by the original Commons engine. Existing saves use the same
database path and require no conversion.

To compare or roll back locally, check out `52fbfe1` in a separate worktree, install
HUBE alongside the Commons checkpoint above, and open a **copy** of the save.
Keep the active checkout and save intact while comparing results.

The recovered working-copy release also includes the optional TAG tools and
their tests. Terminal play works with the core dependencies. TAG video processing
uses the `vision` extra and working FFmpeg/FFprobe binaries.

The book-presentation menu is available through `game play`. It calls the existing
STOP 01 action forms and reads the same world and event log as the original menu
at `game play hube-stop-01`. The optional profile adds self-declared fields to
the actor's metadata through an explicit shared action. The proposer interface
receives detached state and may select IDs from validated moves. The game ships
with deterministic suggestions and works without an AI service.

Run the full HUBE suite with `python -m pip install '.[vision,test]'` followed by
`python -m pytest -ra`. Install working FFmpeg and FFprobe to exercise the video
tests. The default loader on the validation Mac needed a process-scoped
`DYLD_FALLBACK_LIBRARY_PATH` pointing to the installed compatible libraries.
The launch and complete STOP 01 journey are covered by
`tests/test_mission_release.py`.
