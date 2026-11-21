"""Hube's domain hooks for the shared Game-Gamer transaction runtime."""

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from . import projections
from ._shared import WorldEngine
from .capacity import possibilities
from .command_contracts import command_spec
from .command_identity import same_command
from .commands import CommandPlan
from .policies import authorize_actor
from .requirements import evaluate_requirements, is_feasible

EPOCH = datetime.fromisoformat('2026-10-06T00:00:00+00:00')


class Game(WorldEngine):
    def validate(self, command):
        """Validate against this world without recording an action."""
        try:
            spec = command_spec(command)
            prior = self._prior(command)
            if prior:
                if not same_command(prior['command'], command):
                    raise ValueError('key_conflict')
                return []
            if is_feasible(self._world):
                raise ValueError('game_over')
            authorize_actor(self._world, command)
            self._plan(command, spec)
            return []
        except KeyError:
            return ['missing_field']
        except (TypeError, OverflowError):
            return ['invalid_payload']
        except ValueError as error:
            return [str(error)]

    def _plan(self, command, spec):
        plan = CommandPlan(
            self.get_world(), command, self.revision + 1, self._timestamp()
        )
        return plan, spec.handler(plan)

    def _prepare(self, command):
        plan, summary = self._plan(command, command_spec(command))
        world = plan.world
        world['actions'][plan.action_id] = plan.action
        evaluate_requirements(world, plan.timestamp)
        if is_feasible(world):
            target = world['nodes']['event_001']
            target['metadata']['feasibility'] = 'feasible'
            target['updated_at'] = plan.timestamp
            summary = 'event.feasible'
        return world, plan.action_id, summary

    def join(self, label, *, key):
        return self.submit(
            {'key': key, 'kind': 'join', 'actor': 'system', 'label': label}
        )

    def verify(self, subject, *, actor, key, evidence_kind, reference):
        return self.submit(
            {
                'key': key,
                'kind': 'verify',
                'actor': actor,
                'subject': subject,
                'evidence_kind': evidence_kind,
                'reference': reference,
            }
        )

    def evaluate_requirements(self):
        world = self.get_world()
        evaluate_requirements(world, self._timestamp())
        return world['requirements']

    def derive_possibilities(self):
        return possibilities(self.get_world())

    def derive_player_moves(self, actor, *, demand_id=None, explore=False):
        return projections.derive_player_moves(
            self.get_world(), actor, demand_id=demand_id, explore=explore
        )

    def resolve_resources(self, label):
        return projections.resolve_resources(self.get_world(), label)

    def valid_observation_relations(self, source_id, target_id):
        return projections.valid_observation_relations(
            self.get_world(), source_id, target_id
        )

    def project_need(self, demand_id):
        return projections.project_need(self.get_world(), demand_id)

    def project_journey(self, target_id='event_001', *, at=None):
        return self.project_causal_trace(target_id, at=at)

    def project_causal_trace(self, target, terminal_state='feasible', *, at=None):
        from .journey import project_causal_trace

        return project_causal_trace(self, target, terminal_state, at=at)

    def project(self, view='now', *, at=None, time=None):
        world = (
            self.world_at(event=at, time=time)
            if at is not None or time is not None
            else self.get_world()
        )
        if view in {'log', 'timeline'}:
            cutoff = datetime.fromisoformat(time) if time is not None else None
            return deepcopy(
                [
                    e
                    for e in self._log
                    if (at is None or e['sequence'] <= at)
                    and (
                        cutoff is None
                        or datetime.fromisoformat(e['occurred_at']) <= cutoff
                    )
                ]
            )
        return projections.project_world(world, view)


def load_fixture(name='hube-stop-01'):
    if name != 'hube-stop-01':
        raise ValueError('unknown_fixture')
    world = json.loads(
        (Path(__file__).parent / 'fixtures' / (name + '.json')).read_text()
    )
    game = Game()
    game._commit(game.get_world(), world, 'world.initialized')
    return game
