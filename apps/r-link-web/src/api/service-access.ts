import { API_CONFIG } from './config';

export function apiOrigin(): string {
  return new URL(API_CONFIG.baseURL || '/', window.location.href).origin;
}

const storageKey = () => `r-link-service-key:${apiOrigin()}`;

export function getServiceKey(): string {
  return sessionStorage.getItem(storageKey()) || '';
}

/** The optional server key stays in this tab and is scoped to the API origin. */
export function setServiceKey(value: string): void {
  const key = value.trim();
  if (key) sessionStorage.setItem(storageKey(), key);
  else sessionStorage.removeItem(storageKey());
}
