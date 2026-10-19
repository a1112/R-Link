import { beforeEach, expect, it, vi } from 'vitest';
const request = vi.hoisted(() => vi.fn());
vi.mock('./authenticated-fetch', () => ({ authenticatedFetch: request }));
import { HttpClient } from './client';
import { resetAccount } from './account-access';

beforeEach(() => { request.mockReset(); });

it('preserves existing query parameters and JSON false bodies', async () => {
  request.mockResolvedValue(new Response('{}'));
  await new HttpClient().post('/api/example?first=1', false, { params: { second: 2 } });
  expect(request).toHaveBeenCalledWith('/api/example?first=1&second=2', expect.objectContaining({ body: 'false' }));
});

it('preserves caller cancellation instead of reporting timeout', async () => {
  request.mockRejectedValue(new DOMException('Cancelled', 'AbortError'));
  const controller = new AbortController();
  controller.abort();
  await expect(new HttpClient().get('/api/example', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' });
});

it('rejects an old account response whose body finishes after the account changes', async () => {
  let finish!: (value: unknown) => void;
  let bodyStarted!: () => void;
  const started = new Promise<void>(resolve => { bodyStarted = resolve; });
  const response = new Response('{}');
  vi.spyOn(response, 'json').mockImplementation(() => {
    bodyStarted(); return new Promise(resolve => { finish = resolve; });
  });
  request.mockResolvedValue(response);
  const pending = new HttpClient().get('/api/devices');
  await started; resetAccount(); finish([{ name: 'Previous member private device' }]);
  await expect(pending).rejects.toThrow('已忽略旧响应');
});
