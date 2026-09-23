"""Authenticated shared-folder transfers. No client-supplied absolute paths."""
import tempfile
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from core.auth import require_auth
from core import storage

router = APIRouter(prefix='/api/storage', tags=['storage'], dependencies=[Depends(require_auth)])


class NamedPath(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(default='', max_length=1800)
    name: str = Field(min_length=1, max_length=240)


@router.get('')
def list_files(path: str = Query('', max_length=1800)):
    return storage.list_directory(path)


@router.post('/directory', status_code=201)
def create_directory(data: NamedPath):
    return storage.create_directory(data.path, data.name)


@router.put('/upload', status_code=201)
async def upload(request: Request, name: str = Query(..., max_length=240), path: str = Query('', max_length=1800)):
    storage.validate_name(name)
    storage.relative_parts(path)
    size = 0
    # Stream raw bytes instead of buffering an unbounded multipart form.
    with tempfile.TemporaryFile() as temporary:
        async for chunk in request.stream():
            size += len(chunk)
            if size > storage.MAX_FILE_BYTES:
                raise HTTPException(413, '单文件不能超过 64 MiB')
            await run_in_threadpool(temporary.write, chunk)
        temporary.seek(0)
        return await run_in_threadpool(storage.store_file, path, name, temporary)


@router.get('/download')
def download(path: str = Query(..., max_length=1800)):
    file, name, size = storage.open_download(path)
    def chunks():
        try:
            while chunk := file.read(1024 * 1024):
                yield chunk
        finally:
            file.close()
    return StreamingResponse(chunks(), media_type='application/octet-stream', headers={
        'Content-Disposition': "attachment; filename*=UTF-8''" + quote(name, safe=''),
        'Content-Length': str(size), 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store',
    }, background=BackgroundTask(file.close))


@router.post('/rename')
def rename(data: NamedPath):
    return storage.rename(data.path, data.name)


@router.delete('', status_code=204)
def remove(path: str = Query(..., max_length=1800)):
    storage.remove(path)
    return Response(status_code=204)
