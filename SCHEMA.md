# SCHEMA.md

**Status:** Draft 0.1\
**Purpose:** Minimal semantic and persistence contract for the
render-independent game core\
**Compatibility goal:** Streamlit, terminal, tests, API, and future
clients must consume the same schema and core behavior.

------------------------------------------------------------------------

## 1. Schema philosophy

Schema 0.1 is intentionally small.

The game is modeled as a temporal attributed graph plus an append-only
mutation history. Storage does not need to be a native graph database.

The schema separates:

1.  canonical entities;
2.  canonical relations;
3.  actions/mutations;
4.  claims and evidence;
5.  configuration;
6.  derived projections and possibilities.

Derived views are not canonical persistence.

------------------------------------------------------------------------

## 2. Identifiers

All canonical records require stable opaque identifiers.

Recommended form:

``` text
person_...
place_...
event_...
object_...
resource_...
prop_...
rel_...
action_...
evidence_...
mutation_...
```

Human-readable slugs may coexist with IDs but must not replace stable
IDs.

IDs must not encode localized labels.

------------------------------------------------------------------------

## 3. Common fields

Where applicable:

``` yaml
id: string
schema_version: "0.1"
created_at: datetime
created_by: actor_id | system
updated_at: datetime | null
status: semantic_status
metadata: {}
```

`metadata` is an extension point, not a dumping ground for fields that
have acquired stable semantics.

------------------------------------------------------------------------

## 4. Node

### 4.1 Shape

``` yaml
id: node_id
schema_version: "0.1"
kind: person | collective | place | event | object | resource | proposition
label: string
status: active | provisional | inactive | archived
created_at: datetime
created_by: actor_id | system
updated_at: datetime | null
metadata: {}
```

### 4.2 Semantics

`label` is a human-facing identifier or name, not necessarily localized
application copy.

Examples:

``` yaml
id: person_marco
kind: person
label: Marco
status: active
```

``` yaml
id: event_paris_2027
kind: event
label: Hube inna Paris
status: provisional
```

``` yaml
id: resource_screen_printing
kind: resource
label: screen printing
status: active
```

### 4.3 Node-kind notes

#### `person`

A natural person. Personal-data minimization applies.

#### `collective`

Organization, informal group, venue team, publisher, crew, etc.

#### `place`

City, venue, studio, home, wall, neighborhood, or another meaningful
location.

Precise coordinates are optional and should not be required for
private/sensitive places.

#### `event`

A temporally situated gathering, stop, encounter, or other event-like
target.

#### `object`

A distinguishable physical or digital object that may move, change
custody, or participate in actions.

#### `resource`

A capacity or requirement category.

Examples: accommodation, photography, money, printing, transport,
translation, labor.

#### `proposition`

A possible future object/action/configuration that has not yet become a
canonical event or commitment.

------------------------------------------------------------------------

## 5. Relation

### 5.1 Shape

``` yaml
id: relation_id
schema_version: "0.1"
source_id: node_id
target_id: node_id
kind: relation_kind
status: reported | proposed | committed | verified | rejected | withdrawn | expired
valid_from: datetime | null
valid_until: datetime | null
created_at: datetime
created_by: actor_id | system
evidence_ids: []
attributes: {}
metadata: {}
```

### 5.2 Initial relation vocabulary

The vocabulary is extensible. Initial useful kinds include:

#### Social

``` text
knows
introduced
suggests
collaborates_with
```

#### Capacity / necessity

``` text
offers
needs
requires
has_available
satisfies
```

#### Participation / organization

``` text
participates_in
organizes
hosts
supports
```

#### Spatial

``` text
located_in
available_at
moving_to
```

#### Object relations

``` text
owns
holds
created
translated
transported
```

#### Proposition relations

``` text
proposes
supports_proposition
opposes_proposition
depends_on
```

The relation vocabulary should be registered centrally rather than
scattered through UI code.

### 5.3 Attributes

Relation-specific information belongs in `attributes`.

Example:

``` yaml
source_id: person_giulia
target_id: resource_accommodation
kind: offers
attributes:
  quantity: 2
  unit: bed
  location_id: place_bologna
  available_from: 2026-11-12
  available_until: 2026-11-15
```

When an attribute becomes common across many relation kinds, promote it
into the stable schema.

------------------------------------------------------------------------

## 6. Action

### 6.1 Shape

``` yaml
id: action_id
schema_version: "0.1"
kind: action_kind
actor_ids: []
target_ids: []
status: proposed | accepted | awaiting_verification | verified | rejected | withdrawn
occurred_at: datetime | null
submitted_at: datetime
submitted_by: actor_id
payload: {}
evidence_ids: []
metadata: {}
```

### 6.2 Initial action vocabulary

``` text
observe
invite
introduce
offer
request
propose
commit
confirm
complete
move
translate
contribute
verify
reject
withdraw
```

The command API may expose semantic methods such as `offer()` while
persisting the resulting canonical action.

### 6.3 Action result

Processing an action produces zero or more mutations.

Example:

``` text
action: offer accommodation
    ↓
mutation 1: create resource node if absent
mutation 2: create person --offers--> resource relation
mutation 3: append history record
mutation 4: invalidate/recompute affected possibilities
```

------------------------------------------------------------------------

## 7. Mutation

A mutation is the atomic canonical change produced by an accepted action
or system transition.

### 7.1 Shape

``` yaml
id: mutation_id
schema_version: "0.1"
action_id: action_id | null
kind: create | update | transition | expire | delete_soft
entity_type: node | relation | action | claim | evidence | requirement
entity_id: string
before: {} | null
after: {} | null
occurred_at: datetime
caused_by: actor_id | system
metadata: {}
```

Hard deletion should be exceptional. Historical integrity normally
requires soft deletion or status transition.

Mutations provide the raw material for timeline projections and
historical reconstruction.

------------------------------------------------------------------------

## 8. Claim

Claims allow reported information to exist before verification.

### 8.1 Shape

``` yaml
id: claim_id
schema_version: "0.1"
subject_id: node_id | relation_id | action_id | null
predicate: string
value: any
status: reported | verified | rejected | superseded | withdrawn
reported_by: actor_id
reported_at: datetime
evidence_ids: []
metadata: {}
```

Use claims when uncertainty/provenance matters independently of a
relation's own status.

Do not create claims mechanically for every field.

------------------------------------------------------------------------

## 9. Evidence

### 9.1 Shape

``` yaml
id: evidence_id
schema_version: "0.1"
kind: self_report | player_confirmation | organizer_confirmation | artifact | external_system | system_derived
submitted_by: actor_id | system
submitted_at: datetime
reference: string | null
content_ref: string | null
metadata: {}
```

`reference` may be a human-readable note or external identifier.

`content_ref` may point to a managed file or artifact. The schema must
not assume local filesystem paths.

------------------------------------------------------------------------

## 10. Requirement

Requirements encode conditions for feasibility.

### 10.1 Shape

``` yaml
id: requirement_id
schema_version: "0.1"
owner_id: node_id
kind: relation_exists | minimum_quantity | status_is | custom_rule
required: true
status: unsatisfied | partially_satisfied | satisfied | waived
rule:
  {}
created_at: datetime
created_by: actor_id | system
satisfied_at: datetime | null
satisfied_by: []
metadata: {}
```

### 10.2 Examples

Relation existence:

``` yaml
owner_id: event_paris
kind: relation_exists
rule:
  source_id: event_paris
  relation_kind: hosted_by
```

Equivalent relation direction must be standardized in the relation
registry.

Minimum audience:

``` yaml
owner_id: event_paris
kind: minimum_quantity
rule:
  relation_kind: participates_in
  target_id: event_paris
  minimum: 40
```

Requirements should be evaluable deterministically.

------------------------------------------------------------------------

## 11. Campaign

### 11.1 Shape

``` yaml
id: campaign_hube
schema_version: "0.1"
slug: hube
title: Hube
status: draft | active | completed | archived
default_locale: it
locales:
  - it
  - fr
  - en
starts_at: datetime | null
ends_at: datetime | null
root_node_ids: []
stop_ids: []
configuration:
  {}
```

Campaign configuration should identify entry points into the world, not
duplicate canonical state.

------------------------------------------------------------------------

## 12. Stop

A stop is represented canonically as an `event` node.

Campaign configuration may additionally declare ordered or grouped stop
IDs:

``` yaml
stop_ids:
  - event_italy_01
  - event_italy_02
  - event_paris_01
```

Do not create a separate stop persistence model unless the pilot
demonstrates semantics not captured by events and relations.

------------------------------------------------------------------------

## 13. Initial world fixture

Fixtures are declarative test/setup data.

Indicative Hube fixture:

``` yaml
nodes:
  - id: person_marco
    kind: person
    label: Marco
    status: active

  - id: person_andres
    kind: person
    label: Andres
    status: active

  - id: collective_editor
    kind: collective
    label: Italian editor
    status: active

  - id: event_italy_01
    kind: event
    label: Italy Stop 1
    status: provisional

  - id: event_italy_02
    kind: event
    label: Italy Stop 2
    status: provisional

  - id: event_paris_01
    kind: event
    label: Hube inna Paris
    status: provisional

relations:
  - source_id: person_marco
    target_id: collective_editor
    kind: collaborates_with
    status: verified

campaign:
  id: campaign_hube
  default_locale: it
  locales: [it, fr, en]
  stop_ids:
    - event_italy_01
    - event_italy_02
    - event_paris_01
```

The production fixture will contain only facts the organizers are
willing to assert.

------------------------------------------------------------------------

## 14. Command contract

The core should expose a renderer-independent command boundary.

Indicative interface:

``` python
observe(actor, statement_or_structure)
offer(actor, resource, attributes=None)
need(actor_or_event, resource, attributes=None)
propose(actor, proposition, attributes=None)
act(actor, action_kind, targets=None, payload=None)
verify(actor, subject, evidence=None)
reject(actor, subject, reason=None)
withdraw(actor, subject, reason=None)
```

Free text may enter through `observe()` or another semantic adapter, but
canonical mutation must ultimately use validated structured data.

### Command response

``` yaml
ok: true
command_id: ...
action_id: ...
mutations: []
warnings: []
errors: []
affected_entities: []
possibility_invalidations: []
```

Derived possibilities may be computed synchronously or asynchronously,
but must not be persisted as verified facts.

------------------------------------------------------------------------

## 15. Query / projection contract

Indicative read boundary:

``` python
project_now(scope=None, at=None)
project_timeline(scope=None, start=None, end=None)
project_network(scope=None, at=None, layers=None)
project_people(scope=None, at=None)
project_places(scope=None, at=None)
project_resources(scope=None, at=None)
project_actions(scope=None, at=None)
```

Projection output must be structured data.

No projection may return renderer-specific HTML, Streamlit components,
terminal escape sequences, or visualization-library objects from the
core package.

Adapters may transform projection output for specific renderers.

------------------------------------------------------------------------

## 16. Possibility

Possibilities are derived objects.

### 16.1 Shape

``` yaml
id: derived_or_ephemeral_id
kind: match | missing_capacity | threshold_near | route | introduction | emerging_proposition
source_ids: []
target_ids: []
reason:
  code: string
  parameters: {}
confidence: float | null
generator: deterministic | graph_rule | semantic | ai
created_at: datetime
expires_at: datetime | null
suggested_commands: []
```

Possibilities are disposable and recomputable.

If a player accepts one, the resulting action is canonical.

------------------------------------------------------------------------

## 17. Deterministic possibility rules

Version 0.1 should implement simple rules before AI.

Example:

``` text
event --requires--> resource
person --offers--> same resource
--------------------------------
candidate match
```

Additional filters may include:

-   time compatibility;
-   location compatibility;
-   quantity;
-   status;
-   visibility/access permissions.

These rules should have unit tests independent of any renderer.

------------------------------------------------------------------------

## 18. AI proposal schema

AI must return candidate structured proposals.

Example:

``` yaml
kind: match
source_ids:
  - person_tom
  - person_giulia
target_ids:
  - resource_accommodation
reason:
  code: semantic_need_offer_match
  parameters:
    explanation: >
      Tom reports needing somewhere to sleep in Bologna;
      Giulia reports two available beds in Bologna.
confidence: 0.88
generator: ai
suggested_commands:
  - kind: introduce
    actor_ids: [...]
    target_ids: [...]
```

The explanation is advisory.

The IDs, permissions, and semantic validity must be checked by
deterministic code before presentation or acceptance.

------------------------------------------------------------------------

## 19. Localization schema

Canonical semantics use stable identifiers.

Example:

``` text
relation.offers
relation.needs
action.introduce
status.verified
possibility.match
```

Presentation catalogs provide localized strings.

Example gettext keys:

``` text
game.enter
game.observe
game.offer
game.need
game.propose
game.new_possibility
requirement.satisfied
requirement.unsatisfied
```

Rules:

1.  No user-facing literals in core business logic.
2.  No translated strings as enum values.
3.  User-generated text remains source-language text.
4.  Machine translation, if added, is stored as a derived translation
    with provenance.
5.  Tests must run with at least the default locale and one alternate
    locale.

------------------------------------------------------------------------

## 20. Persistence invariants

The implementation must preserve:

### P1. Stable identity

Canonical entities retain stable IDs across projections and stops.

### P2. Single source of truth

Network/timeline/map renderers do not persist authoritative copies of
world state.

### P3. Mutation provenance

Every canonical state transition is attributable to an action or
explicit system process.

### P4. Temporal legibility

Relevant past state can be reconstructed or queried.

### P5. No AI authority

AI output cannot directly become verified canonical state.

### P6. Idempotency

Retrying the same accepted command with the same idempotency key must
not duplicate canonical effects.

### P7. Validation before mutation

Invalid references, impossible status transitions, and malformed
payloads fail without partial canonical mutation.

### P8. Transactional mutation

A multi-record action either commits its canonical mutation set
coherently or fails coherently.

------------------------------------------------------------------------

## 21. Visibility and access

Schema 0.1 should reserve a visibility field where needed:

``` text
public
campaign
organizers
private
```

Do not build a complex policy engine initially.

However, the core must not assume that every node, relation, need,
offer, or precise location is visible to every player.

Visibility filtering belongs before projection data reaches a renderer.

------------------------------------------------------------------------

## 22. Status-transition examples

### Relation

``` text
reported
  → verified
  → expired

reported
  → rejected

proposed
  → committed
  → verified

committed
  → withdrawn
```

### Action

``` text
proposed
  → accepted
  → awaiting_verification
  → verified
```

or:

``` text
proposed
  → rejected
```

Transitions should be registered and tested, not encoded ad hoc in UI
callbacks.

------------------------------------------------------------------------

## 23. Event log

Every accepted canonical mutation emits an event-log record.

Indicative shape:

``` yaml
id: log_id
occurred_at: datetime
kind: world_mutation
actor_id: person_marco
action_id: action_123
mutation_ids:
  - mutation_456
scope_ids:
  - campaign_hube
  - event_italy_01
summary_code: timeline.capacity_added
summary_parameters:
  actor_id: person_marco
  resource_id: resource_screen_printing
```

`summary_code` is semantic/localizable.

The timeline projection reads this log plus explicitly requested future
commitments/propositions.

------------------------------------------------------------------------

## 24. Testing contract

Minimum test layers:

### Unit

-   schema validation;
-   status transitions;
-   requirement evaluation;
-   deterministic possibility rules;
-   visibility filtering;
-   localization key availability.

### Mutation tests

Given state + command → expected canonical mutations.

### Projection tests

Given canonical state → expected renderer-independent projection.

### Historical tests

Given mutation sequence → expected state at time (t).

### Idempotency tests

Repeated command → one canonical effect.

### Internationalization tests

Core behavior unchanged across locales.

### Acceptance fixture

A Hube scenario must prove:

1.  initial fixture loads;
2.  a player records a new observation;
3.  the graph changes;
4.  a relevant possibility appears;
5.  another player acts on it;
6.  verification changes status;
7.  timeline reflects the sequence;
8.  network projection reflects the new relation;
9.  the same sequence can be executed through a terminal test client
    without Streamlit.

------------------------------------------------------------------------

## 25. Suggested package boundary

Illustrative only:

``` text
game/
├── model/
│   ├── nodes
│   ├── relations
│   ├── actions
│   ├── evidence
│   └── requirements
├── commands/
├── mutations/
├── projections/
├── possibilities/
├── persistence/
├── i18n/
├── validation/
└── fixtures/

clients/
├── streamlit/
└── terminal/
```

The exact module structure may change.

The invariant is dependency direction:

``` text
clients
   ↓
application/core API
   ↓
world model + rules
   ↓
persistence
```

The core must never import Streamlit.

------------------------------------------------------------------------

## 26. Open questions for schema 0.2

Do not resolve these until implementation or pilot evidence requires it:

-   Are missions promoted to first-class entities?
-   Should resources always be nodes, or do some become typed
    attributes?
-   Do observations deserve their own canonical record separate from
    claims/actions?
-   How are quantities and units normalized?
-   How much event sourcing is required versus materialized snapshots?
-   What visibility model is sufficient for underground/pseudonymous
    participation?
-   How are anonymous/provisional people merged safely?
-   When does a proposition become an event?
-   Which relation kinds should be symmetric?
-   What evidence policies differ by action type?
-   How are graph branches scoped across multiple campaigns?
-   How should AI-generated semantic classifications be versioned and
    re-evaluated?

These are deliberately deferred.
