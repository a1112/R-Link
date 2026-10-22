import { afterEach, expect, it, vi } from 'vitest';
import { http } from './client';
import { clashApi } from './clash';

vi.mock('./client', () => ({
  http: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

afterEach(() => vi.resetAllMocks());

it('encodes proxy resource names and keeps the delay timeout explicit', async () => {
  vi.mocked(http.get).mockResolvedValue({ delay: 123 });

  await clashApi.proxyDelay('香港 / 自动', 3500);

  expect(http.get).toHaveBeenCalledWith('/api/clash/proxies/%E9%A6%99%E6%B8%AF%20%2F%20%E8%87%AA%E5%8A%A8/delay', {
    params: { timeout: 3500 },
    signal: undefined,
  });
});

it('sends an explicit managed profile action without claiming local process control', async () => {
  vi.mocked(http.post).mockResolvedValue({});

  await clashApi.startManaged('profile / one');
  await clashApi.stopManaged();

  expect(http.post).toHaveBeenNthCalledWith(1, '/api/clash/managed/start', { profile_id: 'profile / one' });
  expect(http.post).toHaveBeenNthCalledWith(2, '/api/clash/managed/stop');
});

it('passes the expected traffic source only when closing a connection with a guard', async () => {
  vi.mocked(http.delete).mockResolvedValue(undefined);

  await clashApi.closeConnection('connection / one', 'source-a');
  await clashApi.closeConnection('connection / two');

  expect(http.delete).toHaveBeenNthCalledWith(1, '/api/clash/connections/connection%20%2F%20one', { params: { source_id: 'source-a' } });
  expect(http.delete).toHaveBeenNthCalledWith(2, '/api/clash/connections/connection%20%2F%20two', undefined);
});
