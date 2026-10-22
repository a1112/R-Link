import { afterEach, expect, it, vi } from 'vitest';
import { http } from './client';
import { isLiteralUnicastIp, qosApi, validateQoSConfig, type QoSConfig } from './qos';

vi.mock('./client', () => ({
  http: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

afterEach(() => vi.resetAllMocks());

const config: QoSConfig = {
  interface: 'eth0',
  upload_mbps: 100,
  download_mbps: 200,
  policies: [{
    id: 'phone-1',
    label: 'Phone',
    device_id: null,
    ip: '192.168.1.20',
    enabled: true,
    upload_mbps: null,
    download_mbps: 50,
    guaranteed_upload_mbps: 0.1,
    guaranteed_download_mbps: 0.1,
    priority: 3,
  }],
};

it('accepts literal unicast addresses and rejects hostnames or reserved ranges', () => {
  expect(isLiteralUnicastIp('192.168.1.20')).toBe(true);
  expect(isLiteralUnicastIp('2001:db8::20')).toBe(true);
  expect(isLiteralUnicastIp('router.lan')).toBe(false);
  expect(isLiteralUnicastIp('192.168.1.20/24')).toBe(false);
  expect(isLiteralUnicastIp('0.0.0.0')).toBe(false);
  expect(isLiteralUnicastIp('224.0.0.1')).toBe(false);
  expect(isLiteralUnicastIp('::')).toBe(false);
  expect(isLiteralUnicastIp('0:0:0:0:0:0:0:1')).toBe(false);
  expect(isLiteralUnicastIp('::ffff:127.0.0.1')).toBe(false);
  expect(isLiteralUnicastIp('0:0:0:0:0:ffff:7f00:1')).toBe(false);
  expect(isLiteralUnicastIp('::ffff:192.168.1.20')).toBe(true);
  expect(isLiteralUnicastIp('::ff01:2')).toBe(true);
  expect(isLiteralUnicastIp('ff02::1')).toBe(false);
});

it('calls the QoS endpoints with the expected revision contract', async () => {
  vi.mocked(http.get).mockResolvedValue({});
  vi.mocked(http.put).mockResolvedValue({});
  vi.mocked(http.post).mockResolvedValue({});
  vi.mocked(http.delete).mockResolvedValue({});
  const signal = new AbortController().signal;

  await qosApi.status(signal);
  await qosApi.saveConfig(4, config);
  await qosApi.apply(5);
  await qosApi.removeApplied(8);

  expect(http.get).toHaveBeenCalledWith('/api/qos/status', { signal });
  expect(http.put).toHaveBeenCalledWith('/api/qos/config', { expected_revision: 4, config });
  expect(http.post).toHaveBeenCalledWith('/api/qos/apply', { expected_revision: 5 });
  expect(http.delete).toHaveBeenCalledWith('/api/qos/applied', { params: { expected_revision: 8 } });
});

it('rejects zero device limits and accepts null as the shared cap', () => {
  expect(validateQoSConfig(config)).toBeNull();
  expect(validateQoSConfig({ ...config, policies: [{ ...config.policies[0], upload_mbps: 0 }] })).toContain('上传上限');
  expect(validateQoSConfig({ ...config, policies: [{ ...config.policies[0], download_mbps: null }] })).toBeNull();
});

