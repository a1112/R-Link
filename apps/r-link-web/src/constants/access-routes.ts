import { canOperate, type AccountState } from '../api/account-access';
import { routes, type RouteId } from './routes';

export function accessibleRoutes(account: AccountState): RouteId[] {
  if (account.status !== 'ready') return [];
  if (account.config?.mode !== 'oidc') return routes.map(route => route.id);
  const user = account.session?.user;
  if (!account.session?.authenticated || !user || user.disabled || user.role === 'pending') return [];
  if (user.role === 'admin') return routes.map(route => route.id);
  if (canOperate(account)) return ['network', 'remote', 'fabric', 'mesh', 'ssh', 'storage', 'rfile', 'downloads', 'analytics'];
  return ['network', 'remote', 'fabric', 'mesh'];
}
