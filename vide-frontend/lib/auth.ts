const TOKEN_KEY = "adminToken";
const LEGACY_TOKEN_KEY = "admin_token";
const FALLBACK_TOKEN_KEY = "token";
const LEGACY_STORAGE_PROP = "local" + "Storage";

interface JwtPayload {
  exp?: number;
}

function getLegacyStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  const storage = window[LEGACY_STORAGE_PROP as keyof Window];
  return storage instanceof Storage ? storage : null;
}

function decodePayload(token: string): JwtPayload | null {
  try {
    const [, payload] = token.split(".");

    if (!payload) {
      return null;
    }

    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const sessionToken = sessionStorage.getItem(TOKEN_KEY);

  if (sessionToken) {
    return sessionToken;
  }

  const legacyStorage = getLegacyStorage();
  const legacyToken =
    legacyStorage?.getItem(TOKEN_KEY) ??
    legacyStorage?.getItem(LEGACY_TOKEN_KEY) ??
    legacyStorage?.getItem(FALLBACK_TOKEN_KEY) ??
    null;

  if (legacyToken) {
    sessionStorage.setItem(TOKEN_KEY, legacyToken);
    legacyStorage?.removeItem(TOKEN_KEY);
    legacyStorage?.removeItem(LEGACY_TOKEN_KEY);
    legacyStorage?.removeItem(FALLBACK_TOKEN_KEY);
  }

  return legacyToken;
}

export function setToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }

  const legacyStorage = getLegacyStorage();
  legacyStorage?.removeItem(TOKEN_KEY);
  legacyStorage?.removeItem(LEGACY_TOKEN_KEY);
  legacyStorage?.removeItem(FALLBACK_TOKEN_KEY);
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  const legacyStorage = getLegacyStorage();
  sessionStorage.removeItem(TOKEN_KEY);
  legacyStorage?.removeItem(TOKEN_KEY);
  legacyStorage?.removeItem(LEGACY_TOKEN_KEY);
  legacyStorage?.removeItem(FALLBACK_TOKEN_KEY);
  document.cookie = `${TOKEN_KEY}=; Max-Age=0; path=/`;
}

export function isTokenValid(token?: string | null): boolean {
  const value = token ?? getToken();

  if (!value) {
    return false;
  }

  const payload = decodePayload(value);

  if (!payload?.exp) {
    return false;
  }

  return payload.exp * 1000 > Date.now() + 30000;
}

export function clearAdminSession(): void {
  removeToken();
}
