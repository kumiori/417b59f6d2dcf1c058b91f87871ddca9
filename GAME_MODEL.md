# GAME_MODEL.md

**Status:** Draft 0.1\
**Scope:** Render-independent core model for collective "make something"
games\
**Pilot:** Hube campaign, Italy → Italy → Paris\
**Principle:** The game engine must be usable without Streamlit. A
terminal client, tests, API, or another renderer must be able to drive
the same game state and receive the same projections.

---

## 1. Purpose

The game coordinates distributed human capacity toward a desired state
that does not yet exist.

A game begins with a partially populated world: people, relationships,
places, objects, capacities, needs, propositions, commitments, and known
constraints. Players observe and alter that world through consequential
actions.

The engine does not prescribe the final path. It records what is known,
accepts claims and actions, verifies them where necessary, computes
consequences, and exposes newly possible moves.

The canonical loop is:

$$
\text{OBSERVATION} \rightarrow \text{CAPACITY / NECESSITY} \rightarrow \text{ACTION} \rightarrow \text{MUTATION} \rightarrow \text{VERIFICATION} \rightarrow \text{NEW POSSIBILITIES}
$$

The final object may be an event, publication, journey, intervention,
shared resource, collective decision, or another real-world state
transition.

---

## 2. Core design principles

### 2.1 One world, many views

There is one canonical evolving world state.

Timeline, network, map, people view, resources view, missions,
current-state dashboard, and apertures are projections of that state.
They must not become independent stores of truth.

$$
W(t) \longrightarrow \{\Pi_{\mathrm{time}}, \Pi_{\mathrm{people}}, \Pi_{\mathrm{place}}, \Pi_{\mathrm{relation}}, \Pi_{\mathrm{resource}}, \Pi_{\mathrm{action}}\}
$$

### 2.2 Render independence

The core must not depend on Streamlit, HTML, terminal formatting, graph
libraries, or visualization widgets.

A renderer may:

- submit commands;
- request projections;
- display validation errors;
- display candidate possibilities;
- request localized presentation strings.

A renderer must not:

- mutate persistence directly;
- infer canonical state from its own UI state;
- maintain a second authoritative network or timeline;
- encode game rules that are absent from the core.

### 2.3 Consequence before gamification

A move matters because it changes the feasibility or knowledge of the
shared world, not because it earns points.

Scores, badges, streaks, leaderboards, or percentages are not core
concepts.

### 2.4 Offers and needs are symmetric

The game must represent both available capacity and unmet necessity.

A player may contribute by offering something, asking for something,
observing something, introducing someone, proposing something, or
acting.

### 2.5 Claims are not automatically facts

The engine must distinguish:

- reported;
- proposed;
- committed;
- verified;
- rejected;
- withdrawn;
- expired.

Verification may be trivial for low-risk claims and stronger for
commitments, payments, venue constraints, or other consequential facts.

### 2.6 History is first-class

Accepted mutations leave an append-only trace.

Current state may be materialized for efficiency, but it must remain
possible to explain how a relevant state was reached.

### 2.7 Genuine openness

The game must distinguish hard constraints from collective degrees of
freedom.

Participants must be able to alter at least some consequential part of
the path, such as content, connections, resource allocation, sequence,
scale, location, or form.

### 2.8 Smallest viable ontology

Do not model distinctions before the pilot requires them.

Prefer a small generic schema with typed nodes, relations, actions,
claims, and evidence over many domain-specific tables.

### 2.9 AI proposes, humans authorize

AI may interpret language, suggest classifications, identify candidate
matches, cluster observations, or surface latent possibilities.

AI must not directly mutate canonical world state.

AI output is a proposal requiring deterministic validation and, when
consequential, human acceptance.

### 2.10 Internationalization from the core boundary

Semantic identifiers are language-independent.

User-interface strings are localized through gettext-compatible
catalogs.

Human-authored contributions remain in their original language unless an
explicit translation is created.

---

## 3. The world model

At any logical time (t), the world is represented as:

$$
W(t) = (V_t, E_t, A_t, C_t, Q_t)
$$

where:

- $V_t$: entities/nodes known to the game;
- $E_t$: typed temporal relations between entities;
- $A_t$: accepted actions and mutations;
- $C_t$: claims, commitments, and evidence state;
- $Q_t$: game-level configuration and constraints.

The implementation may use relational tables, documents, an event log,
or another persistence strategy. The conceptual contract is graph-like
and temporal regardless of storage technology.

---

## 4. Primitive entities

Draft 0.1 recognizes the following semantic node kinds:

- `person`
- `collective`
- `place`
- `event`
- `object`
- `resource`
- `proposition`

These are intentionally broad.

A `resource` may represent a reusable or consumable capacity such as
money, time, a bed, printing capacity, transport, knowledge, equipment,
or attention.

A `proposition` represents something that could become real but is not
yet an accepted event or commitment.

Node kinds may evolve through schema versions.

---

## 5. Relations

Relations carry much of the meaning of the world.

Examples:

```text
Marco      --knows----------> Person X
Person X   --offers---------> Screen printing
Event A    --needs----------> Photographer
Venue A    --hosts----------> Event A
Book 03    --located_at-----> Paris
Person Y   --introduced-----> Person Z
Person Y   --participates---> Event A
Action 17  --satisfies------> Requirement 4
```

Relations are:

- typed;
- directed unless explicitly defined otherwise;
- temporal;
- attributable to a creator/source;
- capable of carrying status and evidence.

A relation can therefore be true during an interval rather than
timeless.

---

## 6. Observations

An observation is a claim about the world.

Examples:

- "There is a screen-printing workshop in Bologna."
- "Marco knows someone who can host two people."
- "This venue has a projector."
- "I can translate into French."

Observations are important because initial graph population and
subsequent discovery are legitimate game moves.

An observation may:

1.  reference existing nodes;
2.  create provisional nodes;
3.  create provisional relations;
4.  attach evidence;
5.  trigger candidate possibilities.

Observation does not imply verification.

---

## 7. Capacity and necessity

Capacity and necessity are modeled explicitly rather than hidden inside
player profiles.

Canonical forms include:

```text
actor --offers--> resource
actor --needs---> resource
event --requires--> resource
event --has_available--> resource
```

Quantities, dates, locations, scope, and constraints may qualify these
relations.

The core must not assume that heterogeneous resources are commensurable.

€20, a sofa, an introduction, two hours of labor, a van, a translation,
and an audience are distinct capacities.

---

## 8. Actions and mutations

An action is a consequential attempt to change the world.

Conceptually:

$$
W_t \xrightarrow{a} W_{t+1}
$$

Examples:

- invite a person;
- introduce two people;
- commit to attend;
- offer accommodation;
- move an object;
- translate a text;
- pay or pledge money;
- confirm a venue;
- complete a requested task;
- withdraw a future commitment;
- reject a proposed connection.

An action may be:

- proposed;
- accepted;
- awaiting verification;
- verified;
- rejected;
- withdrawn.

The mutation produced by an action must be deterministic once the
accepted action payload is fixed.

---

## 9. Missions / things to do

A mission is not fundamentally a separate game object.

It is a human-readable representation of a desired state transition.

Example:

```text
CURRENT:
Paris event --needs--> projector

TARGET:
Paris event --projector_status--> secured
```

"Find a projector" is one possible rendering of this gap.

A player may satisfy the target in an unexpected way:

- borrow a projector;
- provide one;
- move the event;
- alter the event so projection is unnecessary.

Therefore the core should represent requirements and target conditions,
while mission renderers may suggest concrete actions.

Explicit mission entities may still be introduced where assignment,
ownership, deadlines, or workflow require them.

---

## 10. Requirements, thresholds, and feasibility

A desired object may depend on minimum conditions.

For an event:

```text
required:
  - date confirmed
  - venue confirmed
  - principal participant confirmed
  - books available

optional:
  - exhibition
  - translation booklet
  - accommodation
  - sound
```

A threshold corresponds to a real change in feasibility, not an
arbitrary score.

For a target object (X):

$$
\operatorname{feasible}(X,t) = \bigwedge_{r \in R_{\min}(X)} \operatorname{satisfied}(r,t)
$$

When feasibility changes, that transition is itself recorded in history
and may unlock new possibilities.

---

## 11. Verification

Verification separates world-writing from truth claims.

Possible evidence modes include:

- self report;
- another player's confirmation;
- organizer confirmation;
- artifact/document;
- external system;
- system-derived fact.

Verification policy is configurable by relation/action type.

The game should not demand heavyweight verification for ordinary
low-risk observations.

The core must nevertheless preserve provenance sufficiently to answer:

> Who asserted this, when, on what basis, and what is its current
> status?

---

## 12. Possibilities

A possibility is a candidate next move inferred from current state.

Examples:

- a need matches an offer;
- a person can introduce another person relevant to a requirement;
- an object can travel along an existing route;
- a threshold is one condition away from satisfaction;
- several observations suggest a new proposition;
- a previously impossible branch has become feasible.

Possibilities are derived, not canonical facts.

They may be produced by:

1.  deterministic rules;
2.  graph queries;
3.  semantic matching;
4.  AI interpretation.

A possibility becomes consequential only when a player or authorized
process acts on it.

---

## 13. AI boundary

The AI layer is a possibility detector and semantic interpreter.

Preferred pipeline:

$$
\text{world state} \rightarrow \text{candidate interpretation/match} \rightarrow \text{validation} \rightarrow \text{human decision} \rightarrow \text{canonical mutation}
$$

AI may:

- classify free text into candidate semantic concepts;
- suggest existing nodes that a statement may refer to;
- suggest new provisional nodes;
- match offers and needs;
- identify missing capacities;
- suggest emerging propositions;
- summarize relevant local state.

AI may not:

- silently create verified facts;
- silently commit people;
- silently change resource ownership;
- silently satisfy requirements;
- silently create irreversible external actions.

All AI proposals must be inspectable.

---

## 14. Temporal model

The world contains several temporal statuses:

- happened;
- currently true;
- committed;
- scheduled;
- planned;
- possible;
- expired;
- withdrawn.

The timeline is a projection over:

- accepted mutations;
- verification events;
- commitments;
- scheduled future events;
- propositions when explicitly requested.

It is not a separate calendar database.

The same underlying state must support historical queries such as:

> What did the network look like immediately after Stop 1?

and:

> Which capacities became available between Stop 1 and Stop 2?

---

## 15. Projections

A projection is a read-only transformation of canonical state.

Initial projection families:

### `now`

Current relevant state, unresolved requirements, recent changes, and
available moves.

### `timeline`

Temporal sequence of mutations, commitments, scheduled events, and
selected possibilities.

### `network`

Selected nodes and relations at a requested time or interval.

### `people`

People/collectives and their relationships, capacities, needs,
participation, and provenance.

### `places`

Places and location-related relations.

### `resources`

Offers, needs, availability, commitments, and requirements.

### `actions`

Possible, proposed, active, completed, rejected, or withdrawn actions.

A projection must accept filters rather than assume a particular UI.

---

## 16. Commands

Clients interact with the engine through semantic commands.

Indicative command family:

```text
observe(...)
offer(...)
need(...)
propose(...)
act(...)
verify(...)
reject(...)
withdraw(...)
query(...)
```

A command returns a structured result:

```text
accepted/rejected
validation messages
canonical mutations
new event-log entries
affected projections
new candidate possibilities
```

The exact API is an implementation concern, but the semantic boundary is
not.

---

## 17. Questionnaire / probe relation

A questionnaire is a graph-writing interface.

Question definitions may compile answers into candidate commands.

Examples:

```text
"Dove sei?"
→ located_in(person, place)

"Cosa puoi mettere a disposizione?"
→ offers(person, resource)

"Cosa ti serve?"
→ needs(person, resource)

"Chi dovremmo conoscere?"
→ suggests(person, provisional_person)

"Cosa vorresti far succedere?"
→ proposes(person, proposition)
```

The questionnaire system must not own a parallel interpretation of the
world.

Raw responses may be retained for audit and re-interpretation.

---

## 18. Aperture relation

Aperture is a selective world-reading interface.

Conceptually:

$$
\text{probe}: \text{human} \rightarrow W
$$

$$
\text{aperture}: W \rightarrow \text{human}
$$

Examples of apertures:

- three unresolved needs near a player;
- one new connection;
- a threshold recently crossed;
- one object currently moving;
- one proposition gaining support;
- a newly possible action.

Apertures should expose relevant state without requiring players to
understand the whole graph.

---

## 19. Campaigns, stops, and inheritance

A campaign is a configured game instance evolving across one or more
stops.

A stop is an event or phase inside the same world, not a fresh game
database.

For the pilot:

```text
Hube campaign
├── Italy Stop 1
├── Italy Stop 2
└── Paris
```

State persists across stops.

This enables the key experimental questions:

- Can Stop 1 populate the graph?
- Can capacity discovered at Stop 1 affect Stop 2?
- Can accumulated state help cross into a weaker or multilingual
  network at Paris?

---

## 20. Ending condition

A game or subgame ends when its declared minimum real-world conditions
become satisfied.

The ending is ontological:

```text
desired state: hypothetical
        ↓
minimum feasibility conditions satisfied
        ↓
desired state: executable
```

The renderer may announce:

> THE GAME IS OVER.\
> THE THING STARTS.

The underlying world graph does not disappear. It becomes the inherited
state for subsequent actions or campaigns according to declared rules.

---

## 21. Initial population

The game need not begin from an empty graph.

Organizers may seed known reality:

- existing people;
- known relationships;
- venues;
- dates;
- objects;
- hard constraints;
- confirmed resources;
- existing commitments.

Seeded facts require provenance like any other state.

The purpose is not to pretend the collective creates reality from zero.
The purpose is to reveal and extend the actionable world from a truthful
starting state.

---

## 22. Testability

The engine must be fully exercisable without a graphical renderer.

A minimal test or terminal interaction should be able to:

1.  load a campaign fixture;
2.  inspect a projection;
3.  submit an observation;
4.  create an offer or need;
5.  perform an action;
6.  verify or reject it;
7.  inspect mutations;
8.  inspect the timeline;
9.  inspect the network at a selected time;
10. inspect newly derived possibilities.

A canonical acceptance scenario is:

> Starting from the Hube fixture, a player enters one previously unknown
> fact. The fact changes the world state. The engine derives a new
> possible action. Another player can see and act on that possibility.

---

## 23. Non-goals for 0.1

The first version does not require:

- scoring;
- badges;
- leaderboards;
- complex avatars or profiles;
- a general social feed;
- chat;
- automatic autonomous agents;
- automatic financial transactions;
- full graph editing in the UI;
- sophisticated access-control policy;
- perfect ontology;
- generalized workflow orchestration.

These may be introduced only when a real use case requires them.

---

## 24. Architectural test

For every proposed component, ask:

> Does this component own canonical state?

If yes, it belongs in or behind the world-state engine.

If no, it should normally be a:

- command producer;
- projection;
- renderer;
- validator;
- possibility detector;
- adapter.

This rule is intended to prevent network, timeline, questionnaire,
missions, and map from becoming mutually inconsistent subsystems.
