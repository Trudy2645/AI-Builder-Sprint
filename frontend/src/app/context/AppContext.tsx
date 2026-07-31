import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { translate, type Lang } from "../i18n/translations";

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
  logout: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("ko");
  const [companyName, setCompanyName] = useState<string>("");
  const [currentRole, setCurrentRole] = useState<Role | null>(null);
  const [isDemoSession, setIsDemoSession] = useState(false);

  const login = (role: Role, company?: string, isDemo = false) => {
    setCurrentRole(role);
    setCompanyName(company ?? "");
    setIsDemoSession(isDemo);
  };

  const logout = () => {
    setCurrentRole(null);
    setCompanyName("");
    setIsDemoSession(false);
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
