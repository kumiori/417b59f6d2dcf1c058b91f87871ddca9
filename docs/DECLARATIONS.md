# Structured offers and needs

HUBE's terminal profile editor stages changes locally. A confirmed batch emits
a single `edit_declarations` action through the selected player's GAMER
transaction. Each shared record has a stable ID, actor, direction, category
keys, original text, sharing status, taxonomy version, revision and provenance.
Edits and withdrawals require the current revision. Interest and capability
notes are optional fields separate from offers and needs.

Drafts are private to the editor. The shared transaction stores confirmed
changes and retains earlier shared content in its history. Withdrawal removes
a declaration from the current shared projection. Past events remain
readable. HUBE's local player selection remains a simulated identity boundary.

The reusable `game_gamer_semantics` extension carries the taxonomy, revision
and projection logic alongside HUBE. GAMER 0.2.0 remains pinned and owns
validation dispatch, atomic mutations, SQLite and replay. HUBE supplies its
vocabulary, actor metadata binding, mission links and terminal. The extension
is included in HUBE's wheel and can be moved upstream independently of the
HUBE scenario or save format.

Old `share_profile` payloads and logs remain readable. HUBE exposes each legacy
offer or need string as one uncategorized shared declaration. Editing it in the
terminal keeps its identifier and origin, and materialises the revised record
in the actor's existing metadata. Piped scripts can still use the older
line-based profile prompt. Enter retains the exact stored value. Typing `-`
explicitly clears the field. The legacy offer and need fields accept up to
160 characters. Interests accept the same 320-character limit in both editors.

Declaration content compares status, direction, the set of category keys and
the description with outer whitespace removed. An equivalent submission may
record an action while retaining the stored text, revision and provenance.

## Taxonomy and projections

The packaged [taxonomy](../game/fixtures/declaration-taxonomy.json) defines the
initial ten keys. To supply another vocabulary, set `HUBE_TAXONOMY` to the path
of a JSON document with the same shape before launching. Increment its
`version` when changing the vocabulary and preserve keys for unchanged
concepts. Removed keys are retained on historical records and continue to be
visible by key in projections where they occur.

```sh
python -m game --db .hube.sqlite ecosystem
python -m game --db .hube.sqlite ecosystem --at T5
```

Players are ordered by ID. Declarations are ordered by their original
creation time, then numeric batch position within the creating action,
with stable IDs breaking ties. Revisions retain their original position.
Offer and need matrix cells count shared declarations for the actor and
category. A single multi-tagged declaration contributes one count to each of
its categories. Coverage reports both distinct players and declaration counts.
Potential matrix rows are providers and columns are seekers. Each cell counts
distinct overlapping categories. Diagonal cells are zero. A declared need is
unmatched when none of its categories is offered by another player. The export
identifies uncategorized needs separately and lists all uncategorized
declarations. Private and withdrawn records are excluded from shared current
projections.

## Optional semantic assistant

HUBE accepts a `semantic_assistant(topic, context)` callback. Providers return
ordered keys drawn from the supplied candidates. `categories` proposes tags for
a draft after the player elects to share its text with the assistant.
`connections` ranks directed overlaps using the shared descriptions.
`mission_actions` ranks existing validated moves using declarations and open
conditions. Selecting a connection may expose a validated introduction or
request. The player must separately confirm that game action.

The callback receives detached data and has no engine or session reference.
Invalid identifiers are ignored. Empty results and raised errors fall back to
the deterministic flow. No assistant is configured by default.
