"""Read-only causal support projection; no narration or renderer dependencies.

Follow explicit provenance references, not temporal proximity. This is an audit
of recorded support, not a counterfactual claim about unrecorded human motives.
"""
from collections import Counter
from copy import deepcopy


def project_causal_trace(game, target, terminal_state='feasible', *, at=None):
    if terminal_state != 'feasible':
        raise ValueError('unsupported_terminal_state')
    world = game.world_at(event=at) if at is not None else game.get_world()
    if world['nodes'].get(target, {}).get('kind') != 'event':
        raise ValueError('invalid_target')
    log = game.project('log', at=at)
    initial = game.world_at(event=1)
    nodes, relations = world['nodes'], world['relations']
    requirements = [r for r in world['requirements'].values() if r['owner_id'] == target and r['required']]
    origins = {}
    for entry in log:
        for mutation in entry['mutations']:
            if mutation['before'] is None:
                origins[mutation['entity_id']] = entry
    causal_actions, causal_relations = set(), set()

    def step(kind, record_id, entry, **extra):
        if entry['action_id']:
            causal_actions.add(entry['action_id'])
        if record_id in relations:
            causal_relations.add(record_id)
        return dict(kind=kind, record_id=record_id, sequence=entry['sequence'],
                    actor_id=entry['actor_id'], action_id=entry['action_id'], **extra)

    def origin_step(kind, record_id, **extra):
        return step(kind, record_id, origins[record_id], **extra)

    branches = []
    for requirement in requirements:
        branch = {'id': requirement['id'], 'label': requirement['metadata']['label'],
                  'status': requirement['status'], 'seeded': initial['requirements'].get(requirement['id'], {}).get('status') == 'satisfied',
                  'paths': []}
        for support_id in requirement['satisfied_by']:
            support = relations[support_id]
            if support['status'] != 'verified':
                continue
            if support['kind'] != 'satisfies':
                branch['paths'].append({'provider_id': support['source_id'], 'resource_id': support['target_id'],
                                        'steps': [origin_step('seeded', support_id, evidence_ids=support['evidence_ids'])]})
                continue
            attrs = support['attributes']
            offer = relations[attrs['offer_id']]
            demand = relations[attrs['demand_id']]
            steps = [origin_step('needed', demand['id'])]
            for nid in (support['source_id'], attrs.get('asset_id')):
                if nid and nid not in initial['nodes']:
                    steps.append(origin_step('discovered', nid))
            request_id = offer['attributes'].get('request_id')
            if request_id:
                request = relations[request_id]
                context_id = request['attributes'].get('via_relation_id')
                if context_id:
                    context = relations[context_id]
                    steps.append(origin_step('introduced' if context['kind'] == 'introduced' else 'observed', context_id,
                                             status=context['status'], source_id=context['source_id'], target_id=context['target_id']))
                steps.append(origin_step('requested', request_id, recipient_id=request['target_id']))
            steps.append(origin_step('offered', offer['id']))
            steps.append(origin_step('connected', support_id))
            for entry in log:
                for mutation in entry['mutations']:
                    if mutation['entity_id'] == support_id and mutation['before'] is not None:
                        previous, current = mutation['before']['status'], mutation['after']['status']
                        if previous != current and current in {'committed', 'verified'}:
                            steps.append(step(current, support_id, entry, evidence_ids=mutation['after']['evidence_ids']))
            steps.sort(key=lambda s: s['sequence'])
            branch['paths'].append({'provider_id': support['source_id'], 'resource_id': support['target_id'],
                                    'quantity': attrs['quantity'], 'unit': attrs['unit'], 'steps': steps})
        branches.append(branch)

    def counts(state):
        relevant = [r for r in state['requirements'].values() if r['owner_id'] == target and r['required']]
        return {'people': sum(n['kind'] == 'person' for n in state['nodes'].values()),
                'places': sum(n['kind'] == 'place' for n in state['nodes'].values()),
                'capacities': sum(r['kind'] == 'offers' and r['status'] in {'reported', 'verified'} for r in state['relations'].values()),
                'satisfied': sum(r['status'] == 'satisfied' for r in relevant), 'total': len(relevant)}

    verified = [r for r in relations.values() if r['kind'] == 'satisfies' and r['status'] == 'verified']
    satisfied_needs = []
    for demand in relations.values():
        if demand['kind'] == 'needs' and demand['status'] not in {'withdrawn', 'rejected'}:
            if sum(r['attributes']['quantity'] for r in verified if r['attributes']['demand_id'] == demand['id']) >= demand['attributes']['quantity']:
                satisfied_needs.append(demand['id'])
    people = []
    for person in nodes.values():
        if person['kind'] != 'person':
            continue
        actions = [a for a in world['actions'].values() if a['submitted_by'] == person['id']]
        people.append({'id': person['id'], 'label': person['label'],
                       'actions': dict(Counter(a['kind'] for a in actions)),
                       'causal_actions': dict(Counter(a['kind'] for a in actions if a['id'] in causal_actions))})
    transition = next((e['sequence'] for e in log for m in e['mutations']
                       if m['entity_id'] == target and m['before'] is not None
                       and m['before'].get('metadata', {}).get('feasibility') != 'feasible'
                       and m['after'].get('metadata', {}).get('feasibility') == 'feasible'), None)
    return deepcopy({'target_id': target, 'target_label': nodes[target]['label'],
                     'reached': nodes[target]['metadata'].get('feasibility') == terminal_state,
                     'terminal_sequence': transition, 'requirements': branches,
                     'causal_action_ids': sorted(causal_actions), 'causal_relation_ids': sorted(causal_relations),
                     'people': people, 'labels': {nid: n['label'] for nid, n in nodes.items()},
                     'initial': counts(initial), 'final': counts(world),
                     'changes': {'new_relationships': len(set(relations) - set(initial['relations'])),
                                 'needs_satisfied': len(satisfied_needs),
                                 'offers_activated': len({r['attributes']['offer_id'] for r in verified}),
                                 'introductions': sum(r['kind'] == 'introduced' and r['status'] not in {'withdrawn','rejected'} for r in relations.values()),
                                 'unexpected_resources': sum(n['kind'] == 'resource' and n['id'] not in initial['nodes'] for n in nodes.values())}})
