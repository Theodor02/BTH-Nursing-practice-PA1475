import {
  BrowserCacheLocation,
  InteractionRequiredAuthError,
  PublicClientApplication,
} from "@azure/msal-browser";
import type {
  AccountInfo,
  AuthenticationResult,
  Configuration,
  RedirectRequest,
  SilentRequest,
} from "@azure/msal-browser";

export type MicrosoftAuthAction = "login" | "register";

export type UserRole = "Student" | "Admin" | "SuperAdmin";

type LoginRegistrationResponse = {
  user_id: number;
  created: boolean;
  sso_id: string;
  email: string;
  role: UserRole;
};

export type BackendUser = {
  user_id: number;
  email: string;
  role: UserRole;
  can_access_control_panel: boolean;
  can_manage_users: boolean;
};

function requireViteEnv(name: string): string {
  const value = import.meta.env[name];
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${name} environment variable must be set.`);
  }

  return value.trim();
}

function optionalViteEnv(name: string): string | undefined {
  const value = import.meta.env[name];
  if (typeof value !== "string" || !value.trim()) {
    return undefined;
  }

  return value.trim();
}

const clientId = requireViteEnv("VITE_AZURE_CLIENT_ID");
const tenantId = requireViteEnv("VITE_AZURE_TENANT_ID");
const backendApiScope = requireViteEnv("VITE_AZURE_API_SCOPE");
const redirectUri =
  optionalViteEnv("VITE_AZURE_REDIRECT_URI") ??
  `${window.location.origin}${window.location.pathname}${window.location.search}`;
const apiBaseUrl = (optionalViteEnv("VITE_API_BASE_URL") ?? "").replace(/\/+$/, "");
const pendingMicrosoftAuthActionKey = "fokuslokus.pendingMicrosoftAuthAction";

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: BrowserCacheLocation.LocalStorage,
  },
};

const loginRequest: RedirectRequest = {
  scopes: ["openid", "profile", "email", backendApiScope],
  prompt: "select_account",
};

const registerRequest: RedirectRequest = {
  ...loginRequest,
  prompt: "create",
};

const msalInstance = new PublicClientApplication(msalConfig);
let hasInitialized = false;

async function ensureInitialized(): Promise<void> {
  if (!hasInitialized) {
    await msalInstance.initialize();
    hasInitialized = true;
  }
}

async function acquireBackendAccessToken(
  explicitAccount?: AccountInfo | null,
): Promise<string> {
  await ensureInitialized();

  const account = explicitAccount ?? ensureActiveAccount();
  if (!account) {
    throw new Error("No active Microsoft session is available.");
  }

  const silentRequest: SilentRequest = {
    account,
    scopes: [backendApiScope],
  };

  try {
    const result = await msalInstance.acquireTokenSilent(silentRequest);
    return result.accessToken;
  } catch (error) {
    if (!(error instanceof InteractionRequiredAuthError)) {
      throw error;
    }

    const popupResult = await msalInstance.acquireTokenPopup({
      scopes: [backendApiScope],
      account,
      prompt: "select_account",
      overrideInteractionInProgress: true,
    });

    if (popupResult.account) {
      msalInstance.setActiveAccount(popupResult.account);
    }

    return popupResult.accessToken;
  }
}

function resolveApiUrl(path: string): string {
  if (!apiBaseUrl) {
    return path.startsWith("/") ? path : `/${path}`;
  }

  return `${apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
  account?: AccountInfo | null,
  explicitAccessToken?: string,
): Promise<Response> {
  const accessToken = explicitAccessToken ?? await acquireBackendAccessToken(account);
  const headers = new Headers(init.headers);

  headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(resolveApiUrl(path), {
    ...init,
    credentials: "include",
    headers,
  });
}

function ensureActiveAccount(): AccountInfo | null {
  const activeAccount = msalInstance.getActiveAccount();
  if (activeAccount) {
    return activeAccount;
  }

  const firstKnownAccount = msalInstance.getAllAccounts()[0] ?? null;
  if (firstKnownAccount) {
    msalInstance.setActiveAccount(firstKnownAccount);
  }

  return firstKnownAccount;
}

function setPendingMicrosoftAuthAction(action: MicrosoftAuthAction): void {
  window.sessionStorage.setItem(pendingMicrosoftAuthActionKey, action);
}

function takePendingMicrosoftAuthAction(): MicrosoftAuthAction {
  const pendingAction = window.sessionStorage.getItem(pendingMicrosoftAuthActionKey);
  window.sessionStorage.removeItem(pendingMicrosoftAuthActionKey);

  return pendingAction === "register" ? "register" : "login";
}

export async function handleMicrosoftRedirectResult(): Promise<{
  action: MicrosoftAuthAction;
  result: AuthenticationResult;
} | null> {
  await ensureInitialized();
  const result = await msalInstance.handleRedirectPromise({
    navigateToLoginRequestUrl: false,
  });

  if (!result) {
    return null;
  }

  if (result.account) {
    msalInstance.setActiveAccount(result.account);
  }

  return {
    action: takePendingMicrosoftAuthAction(),
    result,
  };
}

export async function signInWithMicrosoft(): Promise<void> {
  await ensureInitialized();
  setPendingMicrosoftAuthAction("login");
  await msalInstance.loginRedirect(loginRequest);
}

export async function registerWithMicrosoft(): Promise<void> {
  await ensureInitialized();
  setPendingMicrosoftAuthAction("register");
  await msalInstance.loginRedirect(registerRequest);
}

export async function registerSignedInUser(
  account?: AccountInfo | null,
  accessToken?: string,
): Promise<LoginRegistrationResponse> {
  const response = await authenticatedFetch(
    "/api/auth/login",
    { method: "POST" },
    account,
    accessToken,
  );

  if (!response.ok) {
    if (response.status === 429) {
      throw new Error("För många inloggningsförsök. Vänta en stund och försök igen.");
    }

    const errorPayload = await response.json().catch(() => null);
    const backendMessage =
      errorPayload &&
      typeof errorPayload === "object" &&
      "error" in errorPayload &&
      typeof errorPayload.error === "string"
        ? errorPayload.error
        : null;

    throw new Error(
      backendMessage ??
        `Backend login sync failed with status ${response.status}.`,
    );
  }

  return (await response.json()) as LoginRegistrationResponse;
}

export async function getSignedInAccount(): Promise<AccountInfo | null> {
  await ensureInitialized();
  return ensureActiveAccount();
}

export async function hasBackendSession(): Promise<boolean> {
  const response = await fetch(resolveApiUrl("/api/sessions"), {
    method: "GET",
    credentials: "include",
  });

  if (response.status === 401) {
    return false;
  }

  if (!response.ok) {
    throw new Error(`Backend session check failed with status ${response.status}.`);
  }

  return true;
}

export async function getCurrentBackendUser(): Promise<BackendUser | null> {
  const response = await fetch(resolveApiUrl("/api/auth/me"), {
    method: "GET",
    credentials: "include",
  });

  if (response.status === 401) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Backend user check failed with status ${response.status}.`);
  }

  return (await response.json()) as BackendUser;
}

export async function deactivateCurrentAccount(): Promise<void> {
  const response = await fetch(resolveApiUrl("/api/auth/me"), {
    method: "DELETE",
    credentials: "include",
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const backendMessage =
      errorPayload &&
      typeof errorPayload === "object" &&
      "error" in errorPayload &&
      typeof errorPayload.error === "string"
        ? errorPayload.error
        : null;

    throw new Error(
      backendMessage ?? `Account deactivation failed with status ${response.status}.`,
    );
  }
}

export function canAccessControlPanel(role: UserRole | null | undefined): boolean {
  return role === "Admin" || role === "SuperAdmin";
}

export function canManageUsers(role: UserRole | null | undefined): boolean {
  return role === "SuperAdmin";
}

export async function logoutBackendSession(): Promise<void> {
  const response = await fetch(resolveApiUrl("/api/auth/logout"), {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Backend logout failed with status ${response.status}.`);
  }
}

export async function logoutMicrosoftSession(): Promise<void> {
  await ensureInitialized();
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0] ?? null;

  msalInstance.setActiveAccount(null);
  await msalInstance.logoutRedirect({
    account,
    postLogoutRedirectUri: window.location.origin,
  });
}

export async function clearMicrosoftSession(): Promise<void> {
  await ensureInitialized();
  const account = ensureActiveAccount();

  await msalInstance.clearCache(account ? { account } : undefined);
  msalInstance.setActiveAccount(null);
}
