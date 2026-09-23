"""Authenticated service APIs used by the Web and Tauri clients."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from core.auth import require_auth
from core.downloads import DownloadInput
from core.domains import DomainInput, DNSInput
from core.tunnels import TunnelInput

router = APIRouter(prefix='/api', tags=['services'], dependencies=[Depends(require_auth)])


def services(request: Request):
    instance = getattr(request.app.state, 'services', None)
    if instance is None or not instance.ready:
        raise HTTPException(503, '后台服务尚未就绪')
    return instance


@router.get('/services')
async def capabilities(request: Request):
    return services(request).capabilities()


@router.get('/audit')
async def audit(request: Request):
    return services(request).state.events()


@router.get('/downloads')
async def downloads(request: Request):
    return services(request).state.list('download')


@router.post('/downloads', status_code=201)
async def create_download(data: DownloadInput, request: Request):
    return await services(request).downloads.create(data)


@router.get('/downloads/{identifier}/file')
async def download_file(identifier: str, request: Request):
    manager = services(request).downloads
    item = manager.state.get('download', identifier)
    if item['state'] != 'completed':
        raise HTTPException(409, '文件尚未下载完成')
    path = manager.path(identifier, '.file')
    if not path.is_file():
        raise HTTPException(404, '下载文件已被移除')
    return FileResponse(path, filename=item['name'], media_type='application/octet-stream',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.post('/downloads/{identifier}/{action}')
async def download_action(identifier: str, action: Literal['pause', 'resume', 'cancel'], request: Request):
    return await services(request).downloads.action(identifier, action)


@router.delete('/downloads/{identifier}', status_code=204)
async def delete_download(identifier: str, request: Request):
    await services(request).downloads.action(identifier, 'delete')
    return Response(status_code=204)


@router.get('/tunnels')
async def tunnels(request: Request):
    return services(request).tunnels.list()


@router.post('/tunnels', status_code=201)
async def create_tunnel(data: TunnelInput, request: Request):
    return await services(request).tunnels.save(data)


@router.put('/tunnels/{identifier}')
async def update_tunnel(identifier: str, data: TunnelInput, request: Request):
    return await services(request).tunnels.save(data, identifier)


@router.post('/tunnels/{identifier}/{action}')
async def tunnel_action(identifier: str, action: Literal['start', 'stop'], request: Request):
    manager = services(request).tunnels
    return await (manager.start(identifier) if action == 'start' else manager.stop(identifier))


@router.get('/tunnels/{identifier}/logs')
async def tunnel_logs(identifier: str, request: Request):
    return {'logs': services(request).tunnels.process(identifier).logs()}


@router.delete('/tunnels/{identifier}', status_code=204)
async def delete_tunnel(identifier: str, request: Request):
    await services(request).tunnels.stop(identifier, delete=True)
    return Response(status_code=204)


@router.get('/domains')
async def domains(request: Request):
    return services(request).state.list('domain')


@router.get('/domains/service')
async def domain_service(request: Request):
    return services(request).domains.status()


@router.post('/domains/service/{action}')
async def domain_service_action(action: Literal['apply', 'stop'], request: Request):
    manager = services(request).domains
    return await (manager.apply() if action == 'apply' else manager.stop())


@router.get('/domains/service/logs')
async def domain_logs(request: Request):
    return {'logs': services(request).domains.process.logs()}


@router.post('/domains', status_code=201)
async def create_domain(data: DomainInput, request: Request):
    return await services(request).domains.save(data)


@router.put('/domains/{identifier}')
async def update_domain(identifier: str, data: DomainInput, request: Request):
    return await services(request).domains.save(data, identifier)


@router.delete('/domains/{identifier}', status_code=204)
async def delete_domain(identifier: str, request: Request):
    await services(request).domains.delete(identifier)
    return Response(status_code=204)


@router.post('/domains/{identifier}/check')
async def check_domain(identifier: str, request: Request):
    return await services(request).domains.check(identifier)


@router.get('/domains/{identifier}/dns')
async def dns_records(identifier: str, request: Request):
    return await services(request).domains.dns(identifier)


@router.post('/domains/{identifier}/dns', status_code=201)
async def create_dns_record(identifier: str, data: DNSInput, request: Request):
    return await services(request).domains.dns(identifier, 'POST', data=data)


@router.delete('/domains/{identifier}/dns/{record_id}', status_code=204)
async def delete_dns_record(identifier: str, record_id: str, request: Request):
    await services(request).domains.dns(identifier, 'DELETE', record_id=record_id)
    return Response(status_code=204)
