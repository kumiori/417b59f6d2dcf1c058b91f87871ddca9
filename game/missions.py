"""Read-only proposal selection from the current player's validated moves."""
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass

from .player import PlayerSession


@dataclass(frozen=True)
class MissionContext:
    actor_id: str
    demand_id: str
    world: dict
    profile: dict
    candidates: tuple[dict, ...]


MissionProposer = Callable[[MissionContext], Sequence[str]]


def mission_proposals(session: PlayerSession, demand_id: str,
                      proposer: MissionProposer | None = None) -> list[dict]:
    """Offer up to three moves. A proposer may only select existing candidate IDs."""
    game = session.game.snapshot()
    actor = session.actor
    log = game.project('log')
    used_keys = {event['command']['key'] for event in log if event['command']}
    key = f'mission-preview-{len(log) + 1}'
    while key in used_keys:
        key += '-'
    candidates = {
        move['id']: move
        for move in game.derive_player_moves(actor, demand_id=demand_id, explore=True)
        if not game.validate({**move['suggested_commands'][0], 'actor': actor, 'key': key})
    }
    fallback = list(candidates.values())[:3]
    if not candidates or proposer is None:
        return fallback

    world = game.get_world()
    context = MissionContext(
        actor, demand_id, world, deepcopy(world['nodes'][actor]['metadata'].get('profile', {})),
        deepcopy(tuple(candidates.values())),
    )
    try:
        selected = proposer(context)
        if isinstance(selected, (str, bytes)) or not isinstance(selected, Sequence):
            return fallback
        ids = dict.fromkeys(move_id for move_id in selected
                            if isinstance(move_id, str) and move_id in candidates)
        return [candidates[move_id] for move_id in list(ids)[:3]] or fallback
    except Exception:
        return fallback
