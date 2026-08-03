import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { LANGUAGE_STORAGE_KEY, initialLanguage, i18n } from "../i18n/i18n";
import { type Lang } from "../i18n/translations";
import { ApiError, apiFetch, getAccessToken, setAccessToken } from "../lib/api";

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
const organizationIdKey = "busanlink.organization_id";

type StoredSession = { role: Role; companyName: string };

function readStoredSession(): StoredSession | null {
  try {
    const value = window.sessionStorage.getItem(sessionKey);
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
  // A remembered UI role alone is not authentication.  Do not render protected
  // pages as logged in after the API token has been removed or expired.
  const authenticatedSession = storedSession && getAccessToken() ? storedSession : null;
  const { t: translate } = useTranslation();
  const [lang, setLangState] = useState<Lang>(initialLanguage);
  const [companyName, setCompanyName] = useState<string>(authenticatedSession?.companyName ?? "");
  const [currentRole, setCurrentRole] = useState<Role | null>(authenticatedSession?.role ?? null);
  const [isDemoSession, setIsDemoSession] = useState(false);

  // The stored UI role is only a convenience.  The authenticated user returned
  // by the server is authoritative, especially after switching demo accounts.
  useEffect(() => {
    if (!authenticatedSession) return;

    let cancelled = false;
    void apiFetch<{ role: Role; display_name: string; organizations: Array<{ id: string }> }>("/me")
      .then((me) => {
        if (cancelled) return;
        const organizationId = me.organizations[0]?.id;
        if (organizationId) window.sessionStorage.setItem(organizationIdKey, organizationId);
        else window.sessionStorage.removeItem(organizationIdKey);

        if (me.role !== authenticatedSession.role) {
          setCurrentRole(me.role);
          setCompanyName(me.display_name);
          window.sessionStorage.setItem(sessionKey, JSON.stringify({ role: me.role, companyName: me.display_name }));
        }
      })
      .catch((error: unknown) => {
        // An expired/invalid token must not leave a misleading protected UI on
        // screen.  Transient server failures keep the current session intact.
        if (!cancelled && error instanceof ApiError && error.code === "AUTH_REQUIRED") logout();
      });

    return () => { cancelled = true; };
  // Run once for the persisted session. Login flows set state explicitly.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setLang = (nextLanguage: Lang) => {
    setLangState(nextLanguage);
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
    document.documentElement.lang = nextLanguage === "ko" ? "ko-KR" : nextLanguage === "en" ? "en-US" : nextLanguage === "ja" ? "ja-JP" : "zh-CN";
    void i18n.changeLanguage(nextLanguage);
  };

  useEffect(() => {
    document.documentElement.lang = lang === "ko" ? "ko-KR" : lang === "en" ? "en-US" : lang === "ja" ? "ja-JP" : "zh-CN";
  }, [lang]);

  const login = (role: Role, company?: string, isDemo = false) => {
    setCurrentRole(role);
    setCompanyName(company ?? "");
    setIsDemoSession(isDemo);
    if (!isDemo) {
      window.sessionStorage.setItem(sessionKey, JSON.stringify({ role, companyName: company ?? "" }));
    }
  };

  const logout = () => {
    setAccessToken(null);
    window.sessionStorage.removeItem(organizationIdKey);
    window.sessionStorage.removeItem(sessionKey);
    setCurrentRole(null);
    setCompanyName("");
    setIsDemoSession(false);
  };

  const loginWithSession = (role: Role, company: string, accessToken: string, organizationId?: string | null) => {
    setAccessToken(accessToken);
    if (organizationId) window.sessionStorage.setItem(organizationIdKey, organizationId);
    else window.sessionStorage.removeItem(organizationIdKey);
    login(role, company, false);
  };

  const value = useMemo<AppContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: string) => translate(key),
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
