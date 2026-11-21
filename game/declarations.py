"""Bind GAMER's declaration extension to HUBE actor metadata and history."""
from functools import lru_cache
import json
import os
from pathlib import Path

from game_gamer_semantics import Taxonomy, project_ecosystem, revise_declarations
from game_gamer_semantics.declarations import MAX_DESCRIPTION, canonical_description

PROFILE_DETAILS = ('interests', 'capabilities')
LEGACY_FIELDS = {'offer': 'offers', 'need': 'needs'}
LEGACY_PROFILE_LIMITS = {'offers': 160, 'needs': 160, 'interests': MAX_DESCRIPTION}


def validate_legacy_profile_value(field, value):
    if (not isinstance(value, str) or not value.strip()
            or len(value) > LEGACY_PROFILE_LIMITS[field] or not value.isprintable()):
        raise ValueError('invalid_profile')


def prepare_legacy_profile(profile, current):
    """Prepare an old-style replacement while preserving untouched stored values."""
    if not isinstance(profile, dict) or set(profile) - LEGACY_PROFILE_LIMITS.keys():
        raise ValueError('invalid_profile')
    values = {}
    for field, value in profile.items():
        validate_legacy_profile_value(field, value)
        values[field] = value if value == current.get(field) else canonical_description(value)
    if 'capabilities' in current:
        values['capabilities'] = current['capabilities']
    return values


def taxonomy():
    configured = os.environ.get('HUBE_TAXONOMY')
    return load_taxonomy(configured)


@lru_cache(maxsize=8)
def load_taxonomy(configured=None):
    path = Path(configured) if configured else Path(__file__).parent / 'fixtures/declaration-taxonomy.json'
    try:
        return Taxonomy.from_dict(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError) as error:
        raise ValueError(f'Invalid declaration taxonomy at {path}') from error


def actor_declarations(world, actor):
    person = world['nodes'][actor]
    metadata = person['metadata']
    legacy = metadata.get('profile', {})
    records = dict(metadata.get('declarations', {}))
    if not any(legacy.get(field) for field in LEGACY_FIELDS.values()):
        return records
    for direction, field in LEGACY_FIELDS.items():
        if not legacy.get(field):
            continue
        prefix = f'legacy:{actor}:{direction}:'
        created = revised = {'actor_id': actor, 'action_id': None, 'at': person['created_at']}
        value, revision = None, 1
        for action in world['actions'].values():
            if action['submitted_by'] != actor:
                continue
            if action['kind'] == 'edit_declarations' and any(
                    target.startswith(prefix) for target in action['target_ids']):
                value = None  # The previous legacy declaration is now a stored record.
            if action['kind'] != 'share_profile':
                continue
            original = action['payload']['profile'].get(field)
            text = canonical_description(original) if original is not None else None
            if text and text != value:
                revised = {'actor_id': actor, 'action_id': action['id'], 'at': action['submitted_at']}
                if value:
                    revision += 1
                else:
                    created, revision = revised, 1
            value = text
        identifier = prefix + (created['action_id'] or 'seed')
        records[identifier] = {
            'id': identifier, 'actor_id': actor, 'direction': direction, 'categories': [],
            'description': legacy[field], 'status': 'shared', 'revision': revision,
            'taxonomy_version': None, 'provenance': {'created': created, 'revised': revised},
            'legacy_field': field,
        }
    return records


def edit_actor_declarations(world, command, action_id, timestamp):
    actor = command['actor']
    existing = actor_declarations(world, actor)
    revised = revise_declarations(existing, command['changes'], taxonomy(),
                                  actor=actor, action_id=action_id, timestamp=timestamp)
    details = command.get('details', {})
    if (not isinstance(details, dict) or set(details) - set(PROFILE_DETAILS)
            or any(value is not None and (
                not isinstance(value, str) or not value.strip()
                or len(value) > MAX_DESCRIPTION or not value.isprintable())
                for value in details.values())):
        raise ValueError('invalid_profile')
    if not command['changes'] and not details:
        raise ValueError('invalid_declaration')
    if not revised and not details:
        return []
    person = world['nodes'][actor]
    metadata = person['metadata']
    profile = dict(metadata.get('profile', {}))
    for record_id in revised:
        legacy_field = existing.get(record_id, {}).get('legacy_field')
        if legacy_field:
            profile.pop(legacy_field, None)
            revised[record_id].pop('legacy_field', None)
    for field, value in details.items():
        if value is None:
            profile.pop(field, None)
        else:
            profile[field] = value
    if profile:
        metadata['profile'] = profile
    else:
        metadata.pop('profile', None)
    if revised:
        metadata.setdefault('declarations', {}).update(revised)
    person['updated_at'] = timestamp
    return list(revised)


def ecosystem(world):
    players = [node['id'] for node in world['nodes'].values()
               if node['kind'] == 'person' and node['metadata'].get('playable')]
    return project_ecosystem(players, (record for actor in players
                                       for record in actor_declarations(world, actor).values()), taxonomy())
