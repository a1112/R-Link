import { http } from './client';
import type { ClashConnection, ClashConnectionMetadata } from './clash';

/** Traffic snapshots may omit fields when the controller cannot provide connection metadata. */
export type ClashTrafficConnectionMetadata = Partial<ClashConnectionMetadata>;

export type ClashTrafficConnection = Omit<ClashConnection, 'metadata'> & {
  metadata?: ClashTrafficConnectionMetadata | null;
};

/** A bounded, point-in-time view of the traffic observed by the API server's Clash core. */
export interface ClashTrafficSnapshot {
  sampled_at: number;
  /** Opaque identity of the API-server/Clash target that produced this sample. */
  source_id: string;
  downloadTotal: number;
  uploadTotal: number;
  connections: ClashTrafficConnection[];
  total_connections: number;
  truncated: boolean;
}

export interface TrafficConnectionRate {
  downloadBps: number;
  uploadBps: number;
}

export type TrafficDeltaReason =
  | 'initial'
  | 'target_changed'
  | 'invalid_interval'
  | 'stale'
  | 'counter_reset'
  | 'invalid_sample';

export interface TrafficDelta {
  ready: boolean;
  reason: TrafficDeltaReason | null;
  elapsedSeconds: number | null;
  downloadBps: number;
  uploadBps: number;
  connectionRates: Record<string, TrafficConnectionRate | null>;
}

function counter(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}

function waiting(reason: TrafficDeltaReason, elapsedSeconds: number | null = null): TrafficDelta {
  return {
    ready: false,
    reason,
    elapsedSeconds,
    downloadBps: 0,
    uploadBps: 0,
    connectionRates: {},
  };
}

/**
 * Convert two cumulative Clash samples to rates.
 *
 * A sample is deliberately a baseline after a target change, counter rollback,
 * invalid interval, or long polling gap. This prevents a reset or a delayed
 * response from being shown as a burst of traffic.
 */
export function calculateTrafficDelta(
  previous: ClashTrafficSnapshot | null,
  current: ClashTrafficSnapshot,
): TrafficDelta {
  if (!previous) return waiting('initial');
  if (previous.source_id !== current.source_id) return waiting('target_changed');

  const elapsedSeconds = current.sampled_at - previous.sampled_at;
  if (!Number.isFinite(elapsedSeconds) || elapsedSeconds <= 0) return waiting('invalid_interval', elapsedSeconds);
  if (elapsedSeconds > 30) return waiting('stale', elapsedSeconds);

  const previousDownload = counter(previous.downloadTotal);
  const previousUpload = counter(previous.uploadTotal);
  const currentDownload = counter(current.downloadTotal);
  const currentUpload = counter(current.uploadTotal);
  if (previousDownload === null || previousUpload === null || currentDownload === null || currentUpload === null) {
    return waiting('invalid_sample', elapsedSeconds);
  }
  if (currentDownload < previousDownload || currentUpload < previousUpload) {
    return waiting('counter_reset', elapsedSeconds);
  }

  const previousConnections = new Map(previous.connections.map(connection => [connection.id, connection]));
  const connectionRates: Record<string, TrafficConnectionRate | null> = {};
  for (const connection of current.connections) {
    const currentDownloadBytes = counter(connection.download);
    const currentUploadBytes = counter(connection.upload);
    if (currentDownloadBytes === null || currentUploadBytes === null) return waiting('invalid_sample', elapsedSeconds);

    const before = previousConnections.get(connection.id);
    if (!before || before.start !== connection.start) {
      // A newly observed connection has no safe baseline yet.
      connectionRates[connection.id] = null;
      continue;
    }

    const previousDownloadBytes = counter(before.download);
    const previousUploadBytes = counter(before.upload);
    if (previousDownloadBytes === null || previousUploadBytes === null) return waiting('invalid_sample', elapsedSeconds);
    if (currentDownloadBytes < previousDownloadBytes || currentUploadBytes < previousUploadBytes) {
      return waiting('counter_reset', elapsedSeconds);
    }
    connectionRates[connection.id] = {
      downloadBps: (currentDownloadBytes - previousDownloadBytes) / elapsedSeconds,
      uploadBps: (currentUploadBytes - previousUploadBytes) / elapsedSeconds,
    };
  }

  return {
    ready: true,
    reason: null,
    elapsedSeconds,
    downloadBps: (currentDownload - previousDownload) / elapsedSeconds,
    uploadBps: (currentUpload - previousUpload) / elapsedSeconds,
    connectionRates,
  };
}

export function connectionHost(connection: ClashTrafficConnection): string {
  const metadata = connection.metadata;
  return metadata?.host || metadata?.destinationIP || '未知目标';
}

export function connectionSource(connection: ClashTrafficConnection): string {
  const metadata = connection.metadata;
  if (!metadata) return '未知来源';
  return `${metadata.sourceIP || '未知来源'}${metadata.sourcePort === undefined ? '' : `:${metadata.sourcePort}`}`;
}

export function connectionProcess(connection: ClashTrafficConnection): string {
  return connection.metadata?.process || connection.process || '未知进程';
}

export function connectionProtocol(connection: ClashTrafficConnection): string {
  return connection.metadata?.network || connection.metadata?.type || '未知协议';
}

/** Search only the user-facing host, source, and process fields. */
export function filterTrafficConnections(
  connections: ClashTrafficConnection[],
  query: string,
  protocol: string,
): ClashTrafficConnection[] {
  const term = query.trim().toLocaleLowerCase();
  return connections.filter(connection => {
    const matchesProtocol = !protocol || connectionProtocol(connection) === protocol;
    if (!matchesProtocol) return false;
    if (!term) return true;
    return [connectionHost(connection), connectionSource(connection), connectionProcess(connection)]
      .some(value => value.toLocaleLowerCase().includes(term));
  });
}

export const trafficApi = {
  snapshot: (signal?: AbortSignal) => http.get<ClashTrafficSnapshot>('/api/clash/traffic', { signal }),
};

export default trafficApi;
