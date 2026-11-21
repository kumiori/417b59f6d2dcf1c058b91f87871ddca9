"""Versioned vocabulary and actor-owned revisions for event-sourced worlds."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re


DIRECTIONS = ('offer', 'need')
MAX_DESCRIPTION = 320
_KEY = re.compile(r'[a-z][a-z0-9_]*')


@dataclass(frozen=True)
class Taxonomy:
    version: str
    categories: tuple[tuple[str, str], ...]

    @classmethod
    def from_dict(cls, document):
        if not isinstance(document, dict):
            raise ValueError('invalid_taxonomy')
        version, categories = document.get('version'), document.get('categories')
        if (
            not isinstance(version, str)
            or not version.strip()
            or not version.isprintable()
            or not isinstance(categories, dict)
            or any(
                not isinstance(key, str)
                or not _KEY.fullmatch(key)
                or not isinstance(label, str)
                or not label.strip()
                or not label.isprintable()
                for key, label in categories.items()
            )
        ):
            raise ValueError('invalid_taxonomy')
        return cls(version, tuple(categories.items()))

    @property
    def keys(self):
        return tuple(key for key, _ in self.categories)

    def label(self, key):
        return dict(self.categories).get(key, key)


def canonical_description(text: str) -> str:
    """Ignore outer whitespace when comparing content and keep the submitted text."""
    return text.strip()


def same_content(current, revised):
    return (
        current['status'] == revised['status']
        and current['direction'] == revised['direction']
        and set(current['categories']) == set(revised['categories'])
        and canonical_description(current['description'])
        == canonical_description(revised['description'])
    )


def declaration_content(change, current, taxonomy, known):
    status = change.get('status')
    if status == 'withdrawn':
        if current is None or set(change) != {'id', 'revision', 'status'}:
            raise ValueError('invalid_declaration')
        return {**current, 'status': status}
    if status != 'shared':
        raise ValueError('invalid_declaration')

    fields = {'status', 'direction', 'categories', 'description'}
    if set(change) != (fields | {'id', 'revision'} if current else fields):
        raise ValueError('invalid_declaration')
    direction, categories, description = (
        change[field] for field in ('direction', 'categories', 'description')
    )
    if (
        direction not in DIRECTIONS
        or (current and direction != current['direction'])
        or not isinstance(categories, list)
        or any(not isinstance(key, str) for key in categories)
        or len(categories) != len(set(categories))
        or not isinstance(description, str)
        or not description.strip()
        or len(description) > MAX_DESCRIPTION
        or not description.isprintable()
    ):
        raise ValueError('invalid_declaration')

    # A revision may retain retired labels. New tags must belong to this vocabulary.
    retained = current['categories'] if current else ()
    if set(categories) - known - set(retained):
        raise ValueError('unknown_category')
    ordered = [key for key in (*taxonomy.keys, *retained) if key in categories]
    return {
        'direction': direction,
        'categories': list(dict.fromkeys(ordered)),
        'description': description,
        'status': status,
        'taxonomy_version': taxonomy.version,
    }


def revise_declarations(
    existing: Mapping[str, dict],
    changes: Sequence[dict],
    taxonomy: Taxonomy,
    *,
    actor: str,
    action_id: str,
    timestamp: str,
) -> dict[str, dict]:
    """Return the proposed revisions for the host to commit in one transaction."""
    if not isinstance(changes, list):
        raise ValueError('invalid_declaration')
    revised = {}
    seen = set()
    known = set(taxonomy.keys)
    for index, change in enumerate(changes, 1):
        if not isinstance(change, dict):
            raise ValueError('invalid_declaration')
        record_id = change.get('id')
        if record_id is not None and not isinstance(record_id, str):
            raise ValueError('invalid_declaration')
        current = None
        if record_id is not None:
            current = existing.get(record_id)
            if current is None or current['actor_id'] != actor or record_id in seen:
                raise ValueError('invalid_declaration')
            seen.add(record_id)
            revision = change.get('revision')
            if type(revision) is not int or revision != current['revision']:
                raise ValueError('stale_declaration')
            if current['status'] != 'shared':
                raise ValueError('invalid_declaration')
        record = declaration_content(change, current, taxonomy, known)
        record_id = record_id or f'declaration:{action_id}:{index}'
        if current is None and record_id in existing:
            raise ValueError('invalid_declaration')
        if current is not None and same_content(current, record):
            continue
        origin = (
            current['provenance']['created']
            if current
            else {
                'actor_id': actor,
                'action_id': action_id,
                'at': timestamp,
            }
        )
        record.update(
            id=record_id,
            actor_id=actor,
            revision=current['revision'] + 1 if current else 1,
            provenance={
                'created': origin,
                'revised': {'actor_id': actor, 'action_id': action_id, 'at': timestamp},
            },
        )
        revised[record_id] = record
    return revised
