"""Actor-bound local play boundary. Identity selection is not authentication."""


class PlayerSession:
    def __init__(self, game, actor, *, hot_seat=False):
        self.game = game
        self.hot_seat = hot_seat
        self._check_actor(actor)
        self._actor = actor

    @property
    def actor(self):
        return self._actor

    def _check_actor(self, actor):
        if not self.game.get_world()['nodes'].get(actor, {}).get('metadata', {}).get('playable'):
            raise ValueError('unknown_player')

    def switch(self, actor):
        if not self.hot_seat:
            raise ValueError('hot_seat_required')
        self._check_actor(actor)
        self._actor = actor

    def submit(self, command):
        if not isinstance(command, dict):
            return {'ok': False, 'errors': ['invalid_command'], 'mutations': []}
        if command.get('actor', self.actor) != self.actor or command.get('kind') == 'join':
            return {'ok': False, 'errors': ['actor_mismatch'], 'mutations': []}
        return self.game.submit({**command, 'actor': self.actor})

    def inbox(self):
        return [r for r in self.game.get_world()['relations'].values()
                if r['kind'] == 'requested' and r['target_id'] == self.actor and r['status'] == 'proposed']

    def possible_moves(self, *, demand_id=None, explore=False):
        return self.game.derive_player_moves(self.actor, demand_id=demand_id, explore=explore)
