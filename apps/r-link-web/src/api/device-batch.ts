import { devicesApi, type Device } from './devices';

/** Limit probes from this client to four, leaving backend slots for other clients. */
export async function probeDevices(devices: Device[], signal: AbortSignal,
  onResult: (device: Device) => void, onProgress: (completed: number) => void) {
  let next = 0;
  let completed = 0;
  const errors: string[] = [];
  const worker = async () => {
    while (!signal.aborted && next < devices.length) {
      const device = devices[next++];
      try {
        const result = await devicesApi.probe(device.id, signal);
        if (!signal.aborted) onResult(result);
      } catch (error) {
        if (!signal.aborted) errors.push(`${device.name}：${error instanceof Error ? error.message : String(error)}`);
      }
      if (!signal.aborted) onProgress(++completed);
    }
  };
  await Promise.all(Array.from({ length: Math.min(4, devices.length) }, worker));
  return { completed, errors, cancelled: signal.aborted };
}
