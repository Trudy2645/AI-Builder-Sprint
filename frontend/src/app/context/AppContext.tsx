import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { translate, type Lang } from "../i18n/translations";
import { setAccessToken } from "../lib/api";

export type Role = "buyer" | "seller";

interface AppContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
  companyName: string;
  setCompanyName: (name: string) => void;
  organizationId: string | null;
  currentRole: Role | null;
  isDemoSession: boolean;
  login: (role: Role, company?: string, isDemo?: boolean) => void;
  loginWithSession: (role: Role, company: string, accessToken: string, organizationId?: string | null) => void;
  logout: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);
const sessionKey = "busan-link-session";

type StoredSession = { role: Role; companyName: string; organizationId?: string | null };

function readStoredSession(): StoredSession | null {
  try {
    const value = window.localStorage.getItem(sessionKey);
    if (!value) return null;
    const parsed: unknown = JSON.parse(value);
    if (
      typeof parsed === "object" && parsed !== null &&
      (parsed as StoredSession).role &&
      ["buyer", "seller"].includes((parsed as StoredSession).role)
    ) return parsed as StoredSession;
  } catch {
    // An invalid local value must never prevent the app from rendering.
  }
  return null;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const storedSession = readStoredSession();
  const [lang, setLang] = useState<Lang>("ko");
  const [companyName, setCompanyName] = useState<string>(storedSession?.companyName ?? "");
  const [organizationId, setOrganizationId] = useState<string | null>(storedSession?.organizationId ?? null);
  const [currentRole, setCurrentRole] = useState<Role | null>(storedSession?.role ?? null);
  const [isDemoSession, setIsDemoSession] = useState(false);

  const login = (role: Role, company?: string, isDemo = false) => {
    setCurrentRole(role);
    setCompanyName(company ?? "");
    setOrganizationId(null);
    setIsDemoSession(isDemo);
    if (!isDemo) {
      window.localStorage.setItem(sessionKey, JSON.stringify({ role, companyName: company ?? "" }));
    }
  };

  const logout = () => {
    setAccessToken(null);
    window.localStorage.removeItem(sessionKey);
    setCurrentRole(null);
    setCompanyName("");
    setOrganizationId(null);
    setIsDemoSession(false);
  };

  const loginWithSession = (role: Role, company: string, accessToken: string, nextOrganizationId?: string | null) => {
    setAccessToken(accessToken);
    setCurrentRole(role);
    setCompanyName(company);
    setOrganizationId(nextOrganizationId ?? null);
    setIsDemoSession(false);
    window.localStorage.setItem(
      sessionKey,
      JSON.stringify({ role, companyName: company, organizationId: nextOrganizationId ?? null }),
    );
  };

  const value = useMemo<AppContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: string) => translate(key, lang),
      companyName,
      setCompanyName,
      organizationId,
      currentRole,
      isDemoSession,
      login,
      loginWithSession,
      logout,
    }),
    [lang, companyName, organizationId, currentRole, isDemoSession],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
