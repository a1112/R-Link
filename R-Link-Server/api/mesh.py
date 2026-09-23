"""R-Link routes for the real NetBird management service."""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from core.auth import require_auth
from core.mesh import (netbird, safe_id, without_key, PeerInput, GroupInput, SetupKeyInput,
                       PolicyInput, NetworkInput, ResourceInput, RouterInput, MANAGED_POLICY_DESCRIPTION)

router = APIRouter(prefix='/api/mesh', tags=['mesh'], dependencies=[Depends(require_auth)])


def audit(request: Request, action: str, identifier: str):
    services = getattr(request.app.state, 'services', None)
    if services and services.ready:
        services.state.audit('mesh.' + action, identifier)


@router.get('/status')
async def status():
    configured = bool(os.getenv('R_LINK_NETBIRD_URL') and os.getenv('R_LINK_NETBIRD_TOKEN'))
    if not configured:
        return {'configured': False, 'reachable': False, 'peers': 0, 'connected': 0,
                'reason': '请设置 R_LINK_NETBIRD_URL 和 R_LINK_NETBIRD_TOKEN'}
    peers = await netbird.request('GET', '/api/peers')
    if not isinstance(peers, list) or any(not isinstance(peer, dict) for peer in peers):
        raise HTTPException(502, 'NetBird 节点响应无效')
    return {'configured': True, 'reachable': True, 'management_url': os.getenv('R_LINK_NETBIRD_URL', '').rstrip('/'), 'peers': len(peers),
            'connected': sum(peer.get('connected') is True for peer in peers), 'reason': None}


@router.get('/peers')
async def peers():
    data = await netbird.request('GET', '/api/peers')
    if not isinstance(data, list) or any(not isinstance(peer, dict) for peer in data):
        raise HTTPException(502, 'NetBird 节点响应无效')
    return [{'id': peer.get('id'), 'name': peer.get('name'), 'ip': peer.get('ip'), 'ipv6': peer.get('ipv6'),
             'connected': peer.get('connected') is True, 'last_seen': peer.get('last_seen'),
             'os': peer.get('os'), 'groups': peer.get('groups', [])} for peer in data]


@router.delete('/peers/{peer_id}', status_code=204)
async def delete_peer(peer_id: str, request: Request):
    await netbird.request('DELETE', '/api/peers/' + safe_id(peer_id))
    audit(request, 'peer.delete', peer_id)
    return Response(status_code=204)


@router.put('/peers/{peer_id}')
async def update_peer(peer_id: str, data: PeerInput, request: Request):
    peer_id = safe_id(peer_id)
    existing = await netbird.request('GET', '/api/peers/' + peer_id)
    if not isinstance(existing, dict):
        raise HTTPException(502, 'NetBird 节点响应无效')
    payload = {key: existing.get(key, False) for key in
               ('ssh_enabled', 'login_expiration_enabled', 'inactivity_expiration_enabled')}
    for key in ('approval_required', 'ip', 'ipv6'):
        if existing.get(key) is not None:
            payload[key] = existing[key]
    payload['name'] = data.name
    result = await netbird.request('PUT', '/api/peers/' + peer_id, payload)
    audit(request, 'peer.update', peer_id)
    return result


@router.get('/groups')
async def groups():
    return await netbird.request('GET', '/api/groups')


@router.post('/groups', status_code=201)
async def create_group(data: GroupInput, request: Request):
    result = await netbird.request('POST', '/api/groups', data.model_dump())
    audit(request, 'group.create', result.get('id', 'group'))
    return result


@router.put('/groups/{group_id}')
async def update_group(group_id: str, data: GroupInput, request: Request):
    group_id = safe_id(group_id)
    existing = await netbird.request('GET', '/api/groups/' + group_id)
    resources = [{'id': value['id'], 'type': value['type']} for value in existing.get('resources', [])]
    result = await netbird.request('PUT', '/api/groups/' + group_id,
                                   dict(data.model_dump(), resources=resources))
    audit(request, 'group.update', group_id)
    return result


@router.delete('/groups/{group_id}', status_code=204)
async def delete_group(group_id: str, request: Request):
    await netbird.request('DELETE', '/api/groups/' + safe_id(group_id))
    audit(request, 'group.delete', group_id)
    return Response(status_code=204)


@router.get('/setup-keys')
async def setup_keys():
    return without_key(await netbird.request('GET', '/api/setup-keys'))


@router.post('/setup-keys', status_code=201)
async def create_setup_key(data: SetupKeyInput, request: Request):
    result = await netbird.request('POST', '/api/setup-keys', data.model_dump())
    audit(request, 'setup-key.create', str(result.get('id', 'new')))
    return JSONResponse(result, status_code=201, headers={'Cache-Control': 'no-store'})


@router.post('/setup-keys/{key_id}/revoke')
async def revoke_setup_key(key_id: str, request: Request):
    key_id = safe_id(key_id)
    item = await netbird.request('GET', '/api/setup-keys/' + key_id)
    result = await netbird.request('PUT', '/api/setup-keys/' + key_id,
                                   {'revoked': True, 'auto_groups': item.get('auto_groups', [])})
    audit(request, 'setup-key.revoke', key_id)
    return without_key(result)


@router.delete('/setup-keys/{key_id}', status_code=204)
async def delete_setup_key(key_id: str, request: Request):
    await netbird.request('DELETE', '/api/setup-keys/' + safe_id(key_id))
    audit(request, 'setup-key.delete', key_id)
    return Response(status_code=204)


@router.get('/policies')
async def policies():
    return await netbird.request('GET', '/api/policies')


@router.post('/policies', status_code=201)
async def create_policy(data: PolicyInput, request: Request):
    result = await netbird.request('POST', '/api/policies', data.payload())
    audit(request, 'policy.create', str(result.get('id', 'new')))
    return result


@router.put('/policies/{policy_id}')
async def update_policy(policy_id: str, data: PolicyInput, request: Request):
    policy_id = safe_id(policy_id)
    existing = await netbird.request('GET', '/api/policies/' + policy_id)
    rules = existing.get('rules') if isinstance(existing, dict) else None
    if (not isinstance(existing, dict) or existing.get('description') != MANAGED_POLICY_DESCRIPTION
            or not isinstance(rules, list) or len(rules) != 1 or not isinstance(rules[0], dict)
            or existing.get('source_posture_checks') or rules[0].get('port_ranges')
            or rules[0].get('authorized_groups') or rules[0].get('sourceResource')
            or rules[0].get('destinationResource')
            or not isinstance(rules[0].get('sources'), list) or len(rules[0]['sources']) != 1
            or not isinstance(rules[0].get('destinations'), list) or len(rules[0]['destinations']) != 1):
        raise HTTPException(409, '仅能在此界面编辑 R-Link 创建的单规则策略')
    result = await netbird.request('PUT', '/api/policies/' + policy_id, data.payload())
    audit(request, 'policy.update', policy_id)
    return result


@router.delete('/policies/{policy_id}', status_code=204)
async def delete_policy(policy_id: str, request: Request):
    await netbird.request('DELETE', '/api/policies/' + safe_id(policy_id))
    audit(request, 'policy.delete', policy_id)
    return Response(status_code=204)


@router.get('/networks')
async def networks():
    return await netbird.request('GET', '/api/networks')


@router.post('/networks', status_code=201)
async def create_network(data: NetworkInput, request: Request):
    result = await netbird.request('POST', '/api/networks', data.model_dump())
    audit(request, 'network.create', str(result.get('id', 'new')))
    return result


@router.put('/networks/{network_id}')
async def update_network(network_id: str, data: NetworkInput, request: Request):
    network_id = safe_id(network_id)
    result = await netbird.request('PUT', '/api/networks/' + network_id, data.model_dump())
    audit(request, 'network.update', network_id)
    return result


@router.delete('/networks/{network_id}', status_code=204)
async def delete_network(network_id: str, request: Request):
    await netbird.request('DELETE', '/api/networks/' + safe_id(network_id))
    audit(request, 'network.delete', network_id)
    return Response(status_code=204)


@router.get('/networks/{network_id}/resources')
async def resources(network_id: str):
    return await netbird.request('GET', '/api/networks/' + safe_id(network_id) + '/resources')


@router.post('/networks/{network_id}/resources', status_code=201)
async def create_resource(network_id: str, data: ResourceInput, request: Request):
    network_id = safe_id(network_id)
    result = await netbird.request('POST', '/api/networks/' + network_id + '/resources', data.model_dump())
    audit(request, 'resource.create', str(result.get('id', 'new')))
    return result


@router.put('/networks/{network_id}/resources/{resource_id}')
async def update_resource(network_id: str, resource_id: str, data: ResourceInput, request: Request):
    network_id, resource_id = safe_id(network_id), safe_id(resource_id)
    result = await netbird.request('PUT', '/api/networks/' + network_id + '/resources/' + resource_id, data.model_dump())
    audit(request, 'resource.update', resource_id)
    return result


@router.delete('/networks/{network_id}/resources/{resource_id}', status_code=204)
async def delete_resource(network_id: str, resource_id: str, request: Request):
    await netbird.request('DELETE', '/api/networks/' + safe_id(network_id) + '/resources/' + safe_id(resource_id))
    audit(request, 'resource.delete', resource_id)
    return Response(status_code=204)


@router.get('/networks/{network_id}/routers')
async def routers(network_id: str):
    return await netbird.request('GET', '/api/networks/' + safe_id(network_id) + '/routers')


@router.post('/networks/{network_id}/routers', status_code=201)
async def create_router(network_id: str, data: RouterInput, request: Request):
    network_id = safe_id(network_id)
    result = await netbird.request('POST', '/api/networks/' + network_id + '/routers', data.payload())
    audit(request, 'router.create', str(result.get('id', 'new')))
    return result


@router.put('/networks/{network_id}/routers/{router_id}')
async def update_router(network_id: str, router_id: str, data: RouterInput, request: Request):
    network_id, router_id = safe_id(network_id), safe_id(router_id)
    result = await netbird.request('PUT', '/api/networks/' + network_id + '/routers/' + router_id, data.payload())
    audit(request, 'router.update', router_id)
    return result


@router.delete('/networks/{network_id}/routers/{router_id}', status_code=204)
async def delete_router(network_id: str, router_id: str, request: Request):
    await netbird.request('DELETE', '/api/networks/' + safe_id(network_id) + '/routers/' + safe_id(router_id))
    audit(request, 'router.delete', router_id)
    return Response(status_code=204)
