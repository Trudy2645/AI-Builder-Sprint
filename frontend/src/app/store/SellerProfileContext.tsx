import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { sellerProfile, type SellerProfile } from "../data/sellerProfile";

interface SellerProfileContextValue {
  profile: SellerProfile;
  updateProfile: (patch: Partial<SellerProfile>) => void;
}

const SellerProfileContext = createContext<SellerProfileContextValue | null>(null);

export function SellerProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<SellerProfile>(sellerProfile);

  const updateProfile = (patch: Partial<SellerProfile>) =>
    setProfile((prev) => ({ ...prev, ...patch }));

  const value = useMemo<SellerProfileContextValue>(
    () => ({ profile, updateProfile }),
    [profile],
  );

  return <SellerProfileContext.Provider value={value}>{children}</SellerProfileContext.Provider>;
}

export function useSellerProfile() {
  const ctx = useContext(SellerProfileContext);
  if (!ctx) throw new Error("useSellerProfile must be used within SellerProfileProvider");
  return ctx;
}
