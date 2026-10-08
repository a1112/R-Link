import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { accountsApi } from '../../api/accounts';
import { resetAccount, updateAccount, type AccountUser } from '../../api/account-access';
import { UserAccessSettings } from './UserAccessSettings';

vi.mock('../../api/accounts', () => ({ accountsApi: { users: vi.fn(), updateUser: vi.fn() } }));
const admin: AccountUser = { id: 'admin', issuer: 'https://idp.example', subject: 'admin-subject', display_name: 'Admin', email: null, role: 'admin', disabled: false };
const pending: AccountUser = { ...admin, id: 'new-member', subject: 'new-subject', display_name: 'New Member', role: 'pending' };

beforeEach(() => {
  resetAccount(); vi.clearAllMocks();
  updateAccount({ status: 'ready', config: { mode: 'oidc', login_enabled: true, desktop_login_enabled: true }, session: { mode: 'oidc', authenticated: true, user: admin, csrf_token: 'csrf', session_context: 'context', expires_at: null }, error: '' });
  vi.mocked(accountsApi.users).mockResolvedValue([pending]);
  vi.mocked(accountsApi.updateUser).mockResolvedValue({ ...pending, role: 'viewer' });
});
afterEach(() => { cleanup(); resetAccount(); });

it('approves an existing pending member without a password or registration flow', async () => {
  render(<UserAccessSettings />);
  const role = await screen.findByRole('combobox', { name: 'New Member的权限角色' });
  expect((role as HTMLSelectElement).value).toBe('pending');
  expect(screen.queryByLabelText(/密码|口令/)).toBeNull();
  fireEvent.change(role, { target: { value: 'viewer' } });
  fireEvent.click(screen.getByRole('button', { name: '保存权限' }));
  await waitFor(() => expect(accountsApi.updateUser).toHaveBeenCalledWith('new-member', { role: 'viewer', disabled: false }));
});

it('can disable a member and reports server enforcement failures', async () => {
  vi.mocked(accountsApi.updateUser).mockRejectedValue(new Error('不能停用最后一位管理员'));
  render(<UserAccessSettings />); await screen.findByText('New Member');
  fireEvent.click(screen.getByRole('checkbox', { name: '停用账户' }));
  fireEvent.click(screen.getByRole('button', { name: '保存权限' }));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', '不能停用最后一位管理员');
  expect(accountsApi.updateUser).toHaveBeenCalledWith('new-member', { role: 'pending', disabled: true });
});
