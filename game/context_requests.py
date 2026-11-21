"""Shared requests and one-use invitation redemption on a local save."""

import hashlib
import re
from hmac import compare_digest

from .capacity import is_open_demand
from .commands import CommandPlan
from .presentations import candidate_node, text_value

TOKEN_HASH = re.compile(r'[0-9a-f]{64}')
RESPONSES = ('help', 'refer', 'question', 'decline')


def token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def request_nodes(world):
    return [
        node
        for node in world['nodes'].values()
        if 'context_request' in node['metadata']
    ]


def invitation_for(world, token):
    digest = token_digest(token)
    for node in request_nodes(world):
        request = node['metadata']['context_request']
        if request['status'] == 'open' and compare_digest(
            request.get('invite_digest', ''), digest
        ):
            return node
    return None


def request_context(world, subject):
    demand = world['relations'].get(subject)
    if demand and is_open_demand(demand):
        return world['nodes'][demand['target_id']]['label']
    return candidate_node(world, subject)['label']


def request_audience(world, actor, recipient_id, invite_digest):
    if recipient_id is not None:
        recipient = world['nodes'].get(recipient_id)
        if (
            invite_digest is not None
            or not recipient
            or recipient['kind'] != 'person'
            or recipient_id == actor
        ):
            raise ValueError('invalid_recipient')
        return {'recipient_id': recipient_id}
    if invite_digest is None:
        return {}
    if not isinstance(invite_digest, str) or not TOKEN_HASH.fullmatch(invite_digest):
        raise ValueError('invalid_invitation')
    if any(
        n['metadata']['context_request'].get('invite_digest') == invite_digest
        for n in request_nodes(world)
    ):
        raise ValueError('invalid_invitation')
    return {'invite_digest': invite_digest}


def create_context_request(plan: CommandPlan) -> str:
    command = plan.command
    subject = command['subject']
    request_context(plan.world, subject)
    question = text_value(command['question'], 'question_required')
    audience = request_audience(
        plan.world,
        plan.actor,
        command.get('recipient_id'),
        command.get('invite_digest'),
    )
    identifier = plan.add_node('proposition', question)
    plan.world['nodes'][identifier]['metadata']['context_request'] = {
        'subject': subject,
        'question': question,
        'inviter': plan.actor,
        'status': 'open',
        **audience,
    }
    plan.action['target_ids'] = [identifier, subject]
    return 'context_request.opened'


def respond_context_request(plan: CommandPlan) -> str:
    command = plan.command
    node = plan.world['nodes'].get(command['subject'], {})
    request = node.get('metadata', {}).get('context_request')
    if not request or request['status'] != 'open':
        raise ValueError('request_not_pending')
    request_context(plan.world, request['subject'])
    authorise_response(plan, request)
    response = command['response']
    if response not in RESPONSES:
        raise ValueError('invalid_response')
    request.update(
        status='answered',
        responder=plan.actor,
        response=response,
        action_id=plan.action_id,
    )
    plan.action['target_ids'] = [node['id'], request['subject']]
    return 'context_request.answered'


def authorise_response(plan, request):
    if (
        request['inviter'] == plan.actor
        or request.get('recipient_id', plan.actor) != plan.actor
    ):
        raise ValueError('recipient_required')
    if 'invite_digest' in request:
        token = plan.command.get('token')
        if not isinstance(token, str) or not compare_digest(
            request['invite_digest'], token_digest(token)
        ):
            raise ValueError('invalid_invitation')
