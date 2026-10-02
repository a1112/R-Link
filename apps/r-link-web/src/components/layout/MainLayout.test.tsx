import { cleanup, fireEvent, render, screen, act } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MainLayout } from './MainLayout';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function viewport(small: boolean) {
  let change: ((event: MediaQueryListEvent) => void) | undefined;
  const query = {
    matches: small,
    addEventListener: vi.fn((_type: string, listener: (event: MediaQueryListEvent) => void) => { change = listener; }),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal('matchMedia', vi.fn(() => query));
  return { resize: (matches: boolean) => act(() => change?.({ matches } as MediaQueryListEvent)), query };
}

it('starts with a compact sidebar on a phone while preserving navigation', () => {
  viewport(true);
  const navigate = vi.fn();
  render(<MainLayout activeRoute="remote" onRouteChange={navigate}><p>设备内容</p></MainLayout>);
  expect(screen.getByRole('button', { name: '展开侧栏' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '虚拟组网' }));
  expect(navigate).toHaveBeenCalledWith('mesh');
});

it('collapses when resized to a phone and removes its resize subscription', () => {
  const view = viewport(false);
  const rendered = render(<MainLayout activeRoute="remote" onRouteChange={() => {}}><p>设备内容</p></MainLayout>);
  expect(screen.getByRole('button', { name: '收起侧栏' })).toBeTruthy();
  view.resize(true);
  expect(screen.getByRole('button', { name: '展开侧栏' })).toBeTruthy();
  rendered.unmount();
  expect(view.query.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
});
