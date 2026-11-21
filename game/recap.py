"""Plain-text renderer for the structured causal journey projection."""
import sys
from .i18n import translator


def render_journey(trace, output=None, locale='en'):
    output = output if output is not None else sys.stdout
    _ = translator(locale)
    labels = trace['labels']
    def write(text=''):
        output.write(str(text) + '\n')
    write(_('HOW THIS BECAME FEASIBLE') if trace['reached'] else _('RECORDED SUPPORT SO FAR'))
    write('─' * 48)
    write(trace['target_label'])
    for branch in trace['requirements']:
        write('  │')
        write('  ├── ' + _(branch['label']) + (' ✓' if branch['status'] == 'satisfied' else ' ?'))
        if not branch['paths']:
            write('  │   ' + _('No verified support yet.'))
        for path in branch['paths']:
            provider = labels[path['provider_id']]
            if 'quantity' in path:
                provider += f" ({path['quantity']} {_(path['unit'])})"
            write('  │   ' + provider)
            for step in path['steps']:
                actor = labels.get(step['actor_id'], _(step['actor_id']))
                detail = _(step['kind'])
                if step['kind'] == 'discovered':
                    detail += ': ' + labels[step['record_id']]
                if step['kind'] in {'introduced', 'observed'}:
                    detail += ': ' + labels[step['source_id']] + ' → ' + labels[step['target_id']]
                    detail += ' (' + _(step['status']) + ')'
                if step.get('recipient_id'):
                    detail += ' → ' + labels[step['recipient_id']]
                write("  │     ↓")
                write(f"  │     {actor}: {detail} [T{step['sequence']}; {step['record_id']}]")
                if step.get('evidence_ids'):
                    write('  │         ' + _('Evidence') + ': ' + ', '.join(step['evidence_ids']))
    write()
    write(_('WHAT WAS NEEDED'))
    write('─' * 48)
    for branch in trace['requirements']:
        if branch['seeded']:
            trail = _('already verified in the seed')
        else:
            paths = []
            for path in branch['paths']:
                stages = list(dict.fromkeys(step['kind'] for step in path['steps']))
                trail = ' → '.join(_(s) for s in stages)
                if len(branch['paths']) > 1:
                    trail += ' (' + labels[path['provider_id']] + ')'
                paths.append(trail)
            trail = ' | '.join(paths) if paths else _('unresolved')
        write(_(branch['label']) + ' → ' + trail)
    write()
    write(_('WHO MOVED THE WORLD'))
    write(_('Causal actions / all recorded actions; observations are not inferred introductions.'))
    for person in trace['people']:
        if person['actions']:
            write(person['label'])
            for kind, count in person['actions'].items():
                write(f"  {_(kind)}: {person['causal_actions'].get(kind, 0)} / {count}")
    write()
    write(_('WHAT CHANGED'))
    for key, label in [('people', 'People'), ('places', 'Places'), ('capacities', 'Active offers'), ('satisfied', 'Verified conditions')]:
        write(f"{_(label)}: {trace['initial'][key]} → {trace['final'][key]}")
    for key, label in [('new_relationships', 'Relationships added (including later withdrawals)'),
                       ('needs_satisfied', 'Personal needs satisfied'), ('offers_activated', 'Offers supporting verified allocations'),
                       ('introductions', 'Reported introductions'), ('unexpected_resources', 'New resource types')]:
        write(f"{_(label)}: {trace['changes'][key]}")
    output.flush()


def offer_recap(game, source=None, output=None, locale='en'):
    source = source if source is not None else sys.stdin
    output = output if output is not None else sys.stdout
    _ = translator(locale)
    output.write(_('See how we got here? [y/N]') + '\n')
    output.flush()
    if source.readline().strip().lower() in {'y', 'yes', 's', 'si', 'sì'}:
        render_journey(game.project_journey('event_001'), output, locale)
