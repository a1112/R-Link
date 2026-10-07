import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { devicesApi, type Device } from '../../api/devices';
vi.mock('../../api/devices', () => ({ devicesApi: { list: vi.fn() } }));
vi.mock('../terminal', () => ({ Terminal: () => <div>Live terminal</div> }));
import { SSHView } from './SSHView';

const server: Device = { id:'cloud',name:'Tencent SSH',host:'175.178.16.90',port:22,username:'ubuntu',device_type:'server',platform:'linux',revision:1,status:'reachable',latency_ms:10,checked_at:null,access_mode:'ssh' };
beforeEach(() => vi.mocked(devicesApi.list).mockResolvedValue([server]));
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('lists registered SSH targets after remount and requests credentials when chosen', async () => {
  render(<SSHView />);
  fireEvent.click(await screen.findByRole('button',{name:'连接 Tencent SSH'}));
  expect(screen.getByDisplayValue('175.178.16.90')).toBeTruthy();
  expect(screen.getByDisplayValue('ubuntu')).toBeTruthy();
  expect(screen.queryByText('Live terminal')).toBeNull();
  cleanup(); render(<SSHView />);
  expect(await screen.findByRole('button',{name:'连接 Tencent SSH'})).toBeTruthy();
});
it('excludes revoked, web-only, and non-SSH discovered targets', async () => {
  vi.mocked(devicesApi.list).mockResolvedValue([server,{...server,id:'web',name:'Web',access_mode:'web'}, {...server,id:'revoked',name:'Revoked',connection_status:'revoked'}, {...server,id:'discovered',name:'Discovered',source:'netbird',access_mode:undefined}]);
  render(<SSHView />);
  expect(await screen.findByRole('button',{name:'连接 Tencent SSH'})).toBeTruthy();
  expect(screen.queryByRole('button',{name:'连接 Web'})).toBeNull();
  expect(screen.queryByRole('button',{name:'连接 Revoked'})).toBeNull();
  expect(screen.queryByRole('button',{name:'连接 Discovered'})).toBeNull();
});
it('shows a source error without preventing new temporary connections', async () => {
  vi.mocked(devicesApi.list).mockRejectedValue(new Error('inventory unavailable'));
  render(<SSHView />);
  expect((await screen.findByRole('alert')).textContent).toContain('inventory unavailable');
  fireEvent.click(screen.getAllByRole('button',{name:'新建连接'})[0]);
  expect(screen.getByPlaceholderText('192.168.1.1')).toBeTruthy();
});
it('imports a selected private key into the current form without storing it', async () => {
  const save = vi.spyOn(Storage.prototype,'setItem');
  render(<SSHView />);
  fireEvent.click(await screen.findByRole('button',{name:'连接 Tencent SSH'}));
  fireEvent.click(screen.getByLabelText('使用私钥认证'));
  const input=screen.getByLabelText('导入私钥文件');
  const key='-----BEGIN OPENSSH PRIVATE KEY-----\nTEST-ONLY\n-----END OPENSSH PRIVATE KEY-----';
  fireEvent.change(input,{target:{files:[new File([key],'test.pem',{type:'text/plain'})]}});
  await waitFor(() => expect((screen.getByRole('textbox',{name:'私钥内容'}) as HTMLTextAreaElement).value).toBe(key));
  fireEvent.click(screen.getByRole('button',{name:'保存'}));
  expect(save).not.toHaveBeenCalled();
  save.mockRestore();
});
it('cancels an unfinished key import when a different target is opened', async () => {
  const readers: { result: string; onload: (() => void) | null; abort: ReturnType<typeof vi.fn> }[] = [];
  class Reader {
    result='-----BEGIN OPENSSH PRIVATE KEY-----\nTEST-ONLY\n-----END OPENSSH PRIVATE KEY-----';
    onload: (()=>void) | null=null; onerror=null;
    abort=vi.fn(); readAsText() {}
    constructor() { readers.push(this); }
  }
  vi.stubGlobal('FileReader',Reader);
  const view=render(<SSHView initialTarget={server} />);
  fireEvent.click(screen.getByLabelText('使用私钥认证'));
  fireEvent.change(screen.getByLabelText('导入私钥文件'),{target:{files:[new File(['key'],'key.pem')]}});
  view.rerender(<SSHView initialTarget={{...server,name:'Other',host:'192.0.2.2'}} />);
  expect(readers[0].abort).toHaveBeenCalled();
  readers[0].onload?.();
  fireEvent.click(screen.getByLabelText('使用私钥认证'));
  expect((screen.getByRole('textbox',{name:'私钥内容'}) as HTMLTextAreaElement).value).toBe('');
});
it('cancels the previous import even when the replacement file is rejected', () => {
  let reader: { onload: (()=>void) | null; abort: ReturnType<typeof vi.fn> };
  class Reader {
    result='-----BEGIN OPENSSH PRIVATE KEY-----\nOLD-TEST-KEY';
    onload: (()=>void) | null=null; onerror=null;
    abort=vi.fn(); readAsText() {}
    constructor() { reader=this; }
  }
  vi.stubGlobal('FileReader',Reader);
  render(<SSHView initialTarget={server} />);
  fireEvent.click(screen.getByLabelText('使用私钥认证'));
  fireEvent.change(screen.getByLabelText('导入私钥文件'),{target:{files:[new File(['key'],'first.pem')]}});
  fireEvent.change(screen.getByLabelText('导入私钥文件'),{target:{files:[new File(['x'.repeat(256*1024+1)],'large.pem')]}});
  expect(reader!.abort).toHaveBeenCalled();
  reader!.onload?.();
  expect((screen.getByRole('textbox',{name:'私钥内容'}) as HTMLTextAreaElement).value).toBe('');
});
