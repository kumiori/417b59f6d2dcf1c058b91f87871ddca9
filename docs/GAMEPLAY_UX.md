# Hube gameplay and terminal architecture

The iteration brief supplies design and acceptance examples. The product
priorities put navigation, editing and disposable worlds first. The Saddle
Pathways screenshot illustrates persistent regions and contextual inspection.

## Component reuse

| Component | Saddle Pathways and Game-Gamer | Hube |
| --- | --- | --- |
| Screen lifecycle | The pinned Game-Gamer package exposes `Screen`, `CursesViewport` and `run_curses` with clipping, redraw, key handling and terminal restoration. | Use those primitives for one interactive session. Keep the line client for scripts. |
| Graph rendering | Saddle Pathways' Montréal explorer calls Game-Gamer's `focus_graph` and `draw_graph`. The newer sibling checkout also has a Braille edge renderer. | Use the packaged renderer with a Hube graph adapter. An upgrade to the newer renderer is a separate dependency change. |
| Directory | Montréal's directory screen composes participant-specific data and a reusable graph renderer. | Compose Hube's profile and contribution read models using the shared viewport and renderer. |
| Forms | Hube already has typed command payloads and line-form builders. | Run those builders in a full-screen form adapter. New actions use Hube's command registry and authorisation policies. |
| Persistence | Game-Gamer owns the transaction and SQLite log. | Interactive routes and drafts stay in the viewport. All shared edits submit through the active player session. |

## Mission and candidate scope

The seeded Bologna journey still reaches STOP 01 feasibility under its six
existing conditions. Alternative presentations have their own location, date,
optional venue and contributions. They draw their checklist labels and minimum
quantities from the mission, while their progress starts at zero and counts
only scoped verified contributions to that candidate. Every candidate can be
inspected independently. Reaching a candidate's threshold has its own receipt
in the candidate view. The legacy end-of-run gate and canonical recap remain
bound to the seeded STOP 01 scenario. This preserves the interpretation of
older events while an official choice among completed candidates remains a
product decision.

## Play and inspect

```sh
# Start STOP 01 on a new save.
new_world=$(mktemp -d)
python -m game --db "$new_world/stop01.sqlite" play

# Explore and act on a disposable in-memory copy.
python -m game --db .hube.sqlite play --sandbox

# Use the line interface.
python -m game --db .hube.sqlite play --line
```

The top-level mission view retains the actor when returning from another
screen. Use arrows and Enter to select, Esc or `b` to return, and `?` for help.
In text fields, characters are literal and F1 opens help without discarding
the text. The mission menu's `r` resets navigation selection. Leaving the
profile draft before sharing discards it. A fresh world uses a new save path.
A disposable simulation uses the supplied history in memory and skips SQLite
writes. It can also begin from the fixture when the supplied path is new.

**Explore the world** opens the book-centred multiplex view. Arrow keys select
nodes, Enter inspects, `c` recentres, `+/-` zooms, `l` changes layer, `f`
filters objects, and `t` opens the same ecosystem in text. Left and right
arrows page through large networks. Requirement markers represent what the
mission needs. Links show declared, proposed, established or inferred
relationships. Exact category overlap produces an inferred link.

**People** uses directory, profile and network regions on a wide terminal.
On a narrow terminal Tab switches the visible region. Use `/` to search.
Enter opens the complete profile and `a` can ask an eligible person about a
mission need. Profiles distinguish unknown information from the absence of a
current shared entry.

**My contributions** opens the saved profile, owned places and shared work.
A place correction keeps the same ID and records the label change in history.
Existing names cannot be duplicated by correction. Authority belongs to the
author, and a confirmed or verified dependency blocks correction. Reported
capacity can be amended while it has no pending request or active allocation.
Withdrawal follows the established Hube withdrawal policy.

**Act** includes presentation proposals and contextual requests. A local
invitation records the inviter, subject and question, and shows a one-use token.
The player redeems it against the same save:

```sh
python -m game --db .hube.sqlite play --invite TOKEN
```

The request is visible before actor selection. The recipient can respond or
explore first. A reply is recorded separately from offers, confirmations and
verification. A local invitation is a continuation of the request within the
existing simulation. Externally accessible invitations require a deployed
service, participant authentication, controlled token exchange and shared
persistence.

## Glossary

| Domain concept | Player-facing wording |
| --- | --- |
| Requirement without an identified contribution | Not found |
| Candidate awaiting agreement | Proposed presentation |
| Requirement with recorded availability | Offered |
| Proposed allocation | Awaiting confirmation |
| Contributor has accepted a commitment | Confirmed |
| Evidence supplied by an independent player | Verified |
| Category overlap | Possibility |
| Declaration or prospect | Something shared |
| Profile | About me |
| Event history | Journey |

The mission header counts a condition as found when it has a compatible
offer, an allocation awaiting confirmation, a confirmation or verified support.
Confirmed counts conditions with committed or partially verified support that
have yet to reach the verified threshold. The condition inspector reports
recorded and compatible offers separately, and gives the failing compatibility
criteria for a recorded offer.

## Complexity and remaining decisions

The gate is `python tools/check_complexity.py`. The existing threshold
baseline covers the legacy line clients and the shared profile editor.
The full-screen views, scoped proposal commands and local request commands
stay within the gate. The client uses the pinned `game-gamer[tui]` extra so
the viewport and graph can account for wide Unicode characters.

| Measure | Before | Iteration 02 |
| --- | ---: | ---: |
| Threshold exceptions | 44 | 43 |
| CLI entry point cyclomatic complexity | 16 | 13 |
| Profile editor control loop cyclomatic complexity | 21 | 16 |
| Full-screen mission control loop cyclomatic complexity | | 5 |

The existing six-condition STOP 01 ending and its causal recap retain their
seeded meaning. Choosing one completed candidate for the confirmed event,
candidate-specific cancellation or withdrawal, and combining several candidate
journeys into a mission-level narrative require separate domain decisions.
Candidate proposals accept a specific date. A date-range proposal and
remotely shareable invitations are follow-up work. Hube uses the packaged
Game-Gamer renderer. The newer Braille renderer in the sibling checkout can
be adopted after a separately verified upstream release.
