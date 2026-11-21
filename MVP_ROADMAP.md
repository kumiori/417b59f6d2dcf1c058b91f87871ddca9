# MVP 0.1 — trajectory and presentation

## Complete

1. Freeze one fictional Hube stop and six explicit minimum conditions.
2. Drive four simulated players through the shared deterministic engine.
3. Preserve atomic canonical mutations, evidence, replay and historical queries.
4. Exercise the complete trajectory through the plain terminal client.
5. Present that same trajectory through a distinct semantic replay driver:
   `game/replay.py`, with keyboard handling in `game/replay_input.py`.

The visible end-to-end demonstration is:

```sh
game simulate hube-stop-01 --paced
# Directly from the checkout:
python3 -m game simulate hube-stop-01 --paced
```

It reveals player statements, graph changes, derived possibilities, provider
commitments, independent verification and threshold crossings, ending with
THE GAME IS OVER / THE THING CAN HAPPEN. Pace, pause, step and speed belong only
to presentation. The four-player reference fixture and final state are unchanged.

6. Add `game play hube-stop-01` for open-ended actor-bound play, with explicit
   `--hot-seat`, join/discovery, owned corrections, requests and recipient responses.
7. Derive `project_journey` / `project_causal_trace` from verified support and
   recorded provenance; offer a read-only recap after the ending.
8. Give human statements 2.5 seconds and system changes 0.5 seconds of base hold,
   with discovery / threshold / ending at 1.5 / 2 / 3 seconds.

9. Make unresolved conditions the main play navigation, with contextual offers,
   normalized resource resolution, typed observations and reversible form navigation.
10. Separate grounded moves from exploration of one need; retain optional needs
    without changing the six ending conditions.

## Acceptance evidence

- Exact final-world equality across engine, terminal client and semantic replay.
- Deterministic event-log reconstruction and historical projections.
- Instant mode never waits; paced modes scale display holds by speed.
- Live pause, arrows / + / -, Enter-to-step and quit through terminal input.
- Terminal settings restored after leaving the replay.
- English and Italian preserve identical canonical semantics.
- Fixed identity cannot answer for another player; hot-seat is explicitly enabled.
- Pending requests persist until their recipient accepts, declines or modifies.
- A complete hot-seat game reaches feasibility through entered commands, without
  running the scenario script; the optional recap reconstructs its own history.
- Unverified/withdrawn allocations and incidental observations are excluded from
  winning paths. Recap reads and historical traces do not mutate the world.

- Andres can add Funding (3000 eur), offer one bed, and use explicit hot-seat
  switching for independent verification and a second provider's bed. Accommodation
  reaches 2/2 verified while Funding stays optional and all six requirements persist.
- Existing duplicate resource nodes are preserved; goal-directed offers target the
  canonical required resource. Invalid or cancelled forms leave no partial nodes.

## Later

Streamlit follows acceptance of this terminal trajectory. Multiple stops, AI,
private participant data, authentication and deployment remain outside MVP 0.1.
