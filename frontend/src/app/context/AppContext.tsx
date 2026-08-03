import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { translate, type Lang } from "../i18n/translations";
import { clearApiSession, getAccessToken, setAccessToken } from "../lib/api";

export type Role = "buyer" | "seller";

interface AppContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
  companyName: string;
  setCompanyName: (name: string) => void;
  currentRole: Role | null;
  isDemoSession: boolean;
  login: (role: Role, company?: string, isDemo?: boolean) => void;
  loginWithSession: (role: Role, company: string, accessToken: string, organizationId?: string | null) => void;
  logout: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);
const sessionKey = "busan-link-session";

type StoredSession = { role: Role; companyName: string };

function displayNameFrom(value: string): string {
  return value.includes("@") ? value.split("@")[0] : value;
}

function readStoredSession(): StoredSession | null {
  try {
    const value = window.localStorage.getItem(sessionKey);
    if (!value) return null;
    const parsed: unknown = JSON.parse(value);
    if (
      typeof parsed === "object" && parsed !== null &&
      (parsed as StoredSession).role &&
      ["buyer", "seller"].includes((parsed as StoredSession).role)
    ) {
      const session = parsed as StoredSession;
      return { ...session, companyName: displayNameFrom(session.companyName) };
    }
  } catch {
    // An invalid local value must never prevent the app from rendering.
  }
  return null;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const storedSession = readStoredSession();
  // A remembered UI role alone is not authentication.  Do not render protected
  // pages as logged in after the API token has been removed or expired.
  const authenticatedSession = storedSession && getAccessToken() ? storedSession : null;
  const [lang, setLang] = useState<Lang>("ko");
  const [companyName, setCompanyName] = useState<string>(authenticatedSession?.companyName ?? "");
  const [currentRole, setCurrentRole] = useState<Role | null>(authenticatedSession?.role ?? null);
  const [isDemoSession, setIsDemoSession] = useState(false);

  const login = (role: Role, company?: string, isDemo = false) => {
    const displayName = displayNameFrom(company ?? "");
    setCurrentRole(role);
    setCompanyName(displayName);
    setIsDemoSession(isDemo);
    if (!isDemo) {
      window.localStorage.setItem(sessionKey, JSON.stringify({ role, companyName: displayName }));
    }
  };

  const logout = () => {
    clearApiSession();
    window.localStorage.removeItem(sessionKey);
    setCurrentRole(null);
    setCompanyName("");
    setIsDemoSession(false);
  };

  const loginWithSession = (role: Role, company: string, accessToken: string, organizationId?: string | null) => {
    setAccessToken(accessToken);
    if (organizationId) window.localStorage.setItem("busanlink.organization_id", organizationId);
    login(role, company, false);
  };

  const value = useMemo<AppContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: string) => translate(key, lang),
      companyName,
      setCompanyName,
      currentRole,
      isDemoSession,
      login,
      loginWithSession,
      logout,
    }),
    [lang, companyName, currentRole, isDemoSession],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
