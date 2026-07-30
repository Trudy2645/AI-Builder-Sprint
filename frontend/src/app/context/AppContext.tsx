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
  login: (role: Role, company?: string) => void;
  logout: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("ko");
  const [companyName, setCompanyName] = useState<string>("");
  const [currentRole, setCurrentRole] = useState<Role | null>(null);

  const login = (role: Role, company?: string) => {
    setCurrentRole(role);
    setCompanyName(
      company ?? (role === "buyer" ? "GlobalTrip Japan" : "해운대 오션스테이"),
    );
  };

  const logout = () => setCurrentRole(null);

  const value = useMemo<AppContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: string) => translate(key, lang),
      companyName,
      setCompanyName,
      currentRole,
      login,
      logout,
    }),
    [lang, companyName, currentRole],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
