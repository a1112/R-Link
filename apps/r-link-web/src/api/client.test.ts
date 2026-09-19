import { beforeEach, expect, it, vi } from 'vitest';
const request = vi.hoisted(() => vi.fn());
vi.mock('./authenticated-fetch', () => ({ authenticatedFetch: request }));
import { HttpClient } from './client';

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
