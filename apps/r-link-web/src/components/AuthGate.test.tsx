import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
const state = vi.hoisted(() => ({ configured: true, getSession: vi.fn(), subscribe: vi.fn(), unsubscribe: vi.fn() }));
vi.mock('../utils/supabase/client', () => ({
  get supabaseConfigured() { return state.configured; },
  supabase: { auth: { getSession: state.getSession, onAuthStateChange: state.subscribe } },
}));
vi.mock('./AuthPage', () => ({ AuthPage: ({ onLogin }: { onLogin: () => void }) => <button onClick={onLogin}>Login callback</button> }));
import { AuthGate } from './AuthGate';
beforeEach(() => {
  state.configured = true;
  state.getSession.mockReset().mockResolvedValue({ data: { session: null }, error: null });
  state.subscribe.mockReset().mockReturnValue({ data: { subscription: { unsubscribe: state.unsubscribe } } });
  state.unsubscribe.mockClear();
});
afterEach(cleanup);
it('keeps management views unmounted until a session event, then handles sign-out', async () => {
  render(<AuthGate><p>Management</p></AuthGate>);
  const login = await screen.findByText('Login callback');
  fireEvent.click(login);
  expect(screen.queryByText('Management')).toBeNull();
  const callback = state.subscribe.mock.calls[0][0];
  act(() => callback('SIGNED_IN', { access_token: 'token' }));
  expect(screen.getByText('Management')).toBeTruthy();
  act(() => callback('SIGNED_OUT', null));
  expect(screen.queryByText('Management')).toBeNull();
});
it('shows setup without reading a persisted session when not configured', () => {
  state.configured = false;
  render(<AuthGate><p>Management</p></AuthGate>);
  expect(screen.getByRole('status').textContent).toContain('尚未配置');
  expect(state.getSession).not.toHaveBeenCalled();
  expect(state.subscribe).not.toHaveBeenCalled();
});
it('does not restore a stale session result after a sign-out event', async () => {
  let resolve!: (value: unknown) => void;
  state.getSession.mockImplementation(() => new Promise(done => { resolve = done; }));
  const view = render(<AuthGate><p>Management</p></AuthGate>);
  act(() => state.subscribe.mock.calls[0][0]('SIGNED_OUT', null));
  await act(async () => resolve({ data: { session: { access_token: 'stale' } }, error: null }));
  expect(screen.queryByText('Management')).toBeNull();
  view.unmount();
  expect(state.unsubscribe).toHaveBeenCalledOnce();
});
