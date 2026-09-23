import { expect, it, vi, afterEach } from 'vitest';
import { devicesApi, type Device } from './devices';
import { probeDevices } from './device-batch';
vi.mock('./devices', () => ({ devicesApi: { probe: vi.fn() } }));
afterEach(() => vi.resetAllMocks());
const targets = Array.from({ length: 9 }, (_, id) => ({ id: String(id), name: `device-${id}` } as Device));

it('limits concurrency and continues after a single device fails', async () => {
  let active = 0;
  let peak = 0;
  vi.mocked(devicesApi.probe).mockImplementation(async id => {
    peak = Math.max(peak, ++active);
    await new Promise(resolve => setTimeout(resolve, 1));
    active--;
    if (id === '2') throw new Error('busy');
    return targets[Number(id)];
  });
  const update = vi.fn();
  const result = await probeDevices(targets, new AbortController().signal, update, () => {});
  expect(peak).toBe(4);
  expect(result.completed).toBe(9);
  expect(result.errors).toEqual(['device-2：busy']);
  expect(update).toHaveBeenCalledTimes(8);
});

it('cancellation does not schedule remaining targets or apply late results', async () => {
  const controller = new AbortController();
  const release: (() => void)[] = [];
  vi.mocked(devicesApi.probe).mockImplementation(id => new Promise(resolve => release.push(() => resolve(targets[Number(id)]))));
  const update = vi.fn();
  const pending = probeDevices(targets, controller.signal, update, () => {});
  expect(devicesApi.probe).toHaveBeenCalledTimes(4);
  controller.abort();
  release.forEach(resolve => resolve());
  expect((await pending).cancelled).toBe(true);
  expect(update).not.toHaveBeenCalled();
  expect(devicesApi.probe).toHaveBeenCalledTimes(4);
});
