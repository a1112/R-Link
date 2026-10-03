"""Authenticated access to the configured R-File services."""
import asyncio
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.requests import ClientDisconnect
from core.auth import require_auth
from core.rfile import MAX_FILE_BYTES
from core.device_sync import drain_task

router = APIRouter(prefix='/api/rfile', tags=['rfile'], dependencies=[Depends(require_auth)])


class DownloadResponse(StreamingResponse):
    def __init__(self, file, *args, **kwargs):
        self.file = file
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # A disconnect while sending headers can bypass both the iterator
            # and Starlette's background task.
            self.file.close()


async def while_connected(request, operation, *, body_read=None, discard_result=None):
    """Cancel an upstream transfer even before an HTTP response can be sent.

    Uploads have one request-body reader. The disconnect listener starts only
    after that reader has finished, so it cannot steal upload chunks.
    """
    async def disconnected():
        if body_read is not None:
            await body_read.wait()
        while True:
            message = await request.receive()
            if message['type'] == 'http.disconnect':
                return

    worker = asyncio.create_task(operation)
    listener = asyncio.create_task(disconnected())
    cleanup = None
    delivered = False

    async def stop():
        nonlocal cleanup
        if cleanup is None:
            listener.cancel()
            if not worker.done():
                worker.cancel()
            cleanup = asyncio.gather(worker, listener, return_exceptions=True)
        await drain_task(cleanup)

    try:
        done, _ = await asyncio.wait({worker, listener}, return_when=asyncio.FIRST_COMPLETED)
        if listener in done:
            raise HTTPException(499, '文件传输已取消')
        result = worker.result()
        await stop()
        delivered = True
        return result
    finally:
        try:
            await stop()
        finally:
            if (not delivered and discard_result and worker.done() and not worker.cancelled()
                    and worker.exception() is None):
                discard_result(worker.result())


@router.get('/status')
def status(request: Request):
    return request.app.state.rfile.status()


@router.post('/refresh')
async def refresh(request: Request):
    return await request.app.state.rfile.refresh()


@router.get('/files')
async def files(request: Request, path: str = Query('', max_length=1800)):
    return await request.app.state.rfile.list_directory(path)


@router.put('/upload', status_code=201)
async def upload(request: Request, name: str = Query(..., max_length=240), path: str = Query('', max_length=1800)):
    length = request.headers.get('content-length')
    if length is not None:
        try:
            if int(length) < 0:
                raise ValueError()
            if int(length) > MAX_FILE_BYTES:
                raise HTTPException(413, '单文件不能超过 64 MiB')
        except ValueError:
            raise HTTPException(400, '文件大小无效') from None
    try:
        body_read = asyncio.Event()
        async def chunks():
            async for chunk in request.stream():
                yield chunk
            body_read.set()
        return await while_connected(request, request.app.state.rfile.upload_stream(path, name, chunks()), body_read=body_read)
    except ClientDisconnect:
        raise HTTPException(499, '文件上传已取消') from None


@router.get('/download')
async def download(request: Request, path: str = Query(..., max_length=1800)):
    file, name, size = await while_connected(request, request.app.state.rfile.download(path),
                                          discard_result=lambda result: result[0].close())
    def chunks():
        try:
            while chunk := file.read(64 * 1024):
                yield chunk
        finally:
            file.close()
    return DownloadResponse(file, chunks(), media_type='application/octet-stream', headers={
        'Content-Disposition': "attachment; filename*=UTF-8''" + quote(name, safe=''),
        'Content-Length': str(size), 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store',
    }, background=BackgroundTask(file.close))
