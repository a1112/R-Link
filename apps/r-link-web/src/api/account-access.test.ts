import { afterEach, beforeEach, expect, it } from 'vitest';
import { expireAccount, resetAccount, serviceBase, topologyAccountScope, updateAccount, type AccountUser } from './account-access';
import { setServiceUrl } from './service-url';

const user: AccountUser = { id: 'member-a', issuer: 'https://auth.example', subject: 'subject', display_name: 'Member A', email: null, role: 'operator', disabled: false };
function session(member: AccountUser, context: string) { updateAccount({ status: 'ready', config: { mode: 'oidc', login_enabled: true, desktop_login_enabled: true }, session: { mode: 'oidc', authenticated: true, user: member, csrf_token: 'csrf', session_context: context, expires_at: null }, error: '' }); }
beforeEach(() => { localStorage.clear(); resetAccount(); setServiceUrl('https://cloud.example/r-link'); });
afterEach(() => { resetAccount(); localStorage.clear(); });

it('isolates account annotations while preserving legacy and returning members layouts', () => {
  const legacyKey = 'r-link-topology:v1:https://cloud.example';
  localStorage.setItem(legacyKey, 'legacy notes');
  session(user, 'session-a'); const scopeA = topologyAccountScope('https://cloud.example');
  const memberKey = `r-link-topology:v1:${scopeA}`; localStorage.setItem(memberKey, 'member A notes');
  session({ ...user, id: 'member-b' }, 'session-b');
  expect(topologyAccountScope('https://cloud.example')).not.toBe(scopeA);
  expect(localStorage.getItem(`r-link-topology:v1:${topologyAccountScope('https://cloud.example')}`)).toBeNull();
  expireAccount(); expect(topologyAccountScope('https://cloud.example')).toBe(`${serviceBase()}:account:anonymous`);
  session(user, 'new-session-a');
  expect(topologyAccountScope('https://cloud.example')).toBe(scopeA);
  expect(localStorage.getItem(memberKey)).toBe('member A notes'); expect(localStorage.getItem(legacyKey)).toBe('legacy notes');
});

it('keeps the exact legacy scope in local and service modes', () => {
  for (const mode of ['local', 'service'] as const) {
    updateAccount({ status: 'ready', config: { mode, login_enabled: false, desktop_login_enabled: false }, session: null, error: '' });
    expect(topologyAccountScope('legacy-origin')).toBe('legacy-origin');
  }
});
