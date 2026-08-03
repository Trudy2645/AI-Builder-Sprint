import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import { getMe, getOrganization, updateMe, updateOrganization, type MeProfile, type OrganizationProfile } from "../lib/api";

export interface SellerProfile {
  company: string;
  bizNo: string;
  ceoName: string;
  contactName: string;
  email: string;
  phone: string;
  address: string;
  supplyFields: string;
  joinedAt: string;
}

const EMPTY_PROFILE: SellerProfile = {
  company: "",
  bizNo: "",
  ceoName: "",
  contactName: "",
  email: "",
  phone: "",
  address: "",
  supplyFields: "",
  joinedAt: "",
};

function dateLabel(value: string): string {
  return value ? value.slice(0, 10).replace(/-/g, ".") : "";
}

function toProfile(me: MeProfile, organization: OrganizationProfile): SellerProfile {
  return {
    company: organization.name,
    bizNo: organization.business_registration_no ?? "",
    ceoName: organization.representative_name ?? "",
    contactName: me.display_name,
    email: me.email ?? "",
    phone: me.phone ?? "",
    address: organization.business_address ?? "",
    supplyFields: organization.supply_categories.join(" · "),
    joinedAt: dateLabel(organization.created_at),
  };
}

interface SellerProfileContextValue {
  profile: SellerProfile;
  loading: boolean;
  updateProfile: (patch: Partial<SellerProfile>) => Promise<void>;
}

const SellerProfileContext = createContext<SellerProfileContextValue | null>(null);

export function SellerProfileProvider({ children }: { children: ReactNode }) {
  const { currentRole } = useApp();
  const [profile, setProfile] = useState<SellerProfile>(EMPTY_PROFILE);
  const [loading, setLoading] = useState(false);
  const organizationId = typeof window === "undefined" ? null : window.localStorage.getItem("busanlink.organization_id");

  const refresh = useCallback(async () => {
    if (currentRole !== "seller" || !organizationId) {
      setProfile(EMPTY_PROFILE);
      return;
    }
    setLoading(true);
    try {
      const [me, organization] = await Promise.all([getMe(), getOrganization(organizationId)]);
      setProfile(toProfile(me, organization));
    } finally {
      setLoading(false);
    }
  }, [currentRole, organizationId]);

  useEffect(() => {
    void refresh().catch(() => setProfile(EMPTY_PROFILE));
  }, [refresh]);

  const updateProfile = useCallback(async (patch: Partial<SellerProfile>) => {
    if (!organizationId) throw new Error("조직 정보가 없습니다.");
    const [me, organization] = await Promise.all([
      updateMe({ display_name: patch.contactName, phone: patch.phone }),
      updateOrganization(organizationId, {
        name: patch.company,
        representative_name: patch.ceoName,
        business_address: patch.address,
        business_registration_no: patch.bizNo,
        supply_categories: patch.supplyFields?.split("·").map((value) => value.trim()).filter(Boolean),
      }),
    ]);
    setProfile(toProfile(me, organization));
  }, [organizationId]);

  const value = useMemo(() => ({ profile, loading, updateProfile }), [profile, loading, updateProfile]);
  return <SellerProfileContext.Provider value={value}>{children}</SellerProfileContext.Provider>;
}

export function useSellerProfile() {
  const context = useContext(SellerProfileContext);
  if (!context) throw new Error("useSellerProfile must be used within SellerProfileProvider");
  return context;
}

export function maskBizNo(value: string): string {
  const parts = value.split("-");
  if (parts.length !== 3) return value;
  const [first, second, last] = parts;
  if (last.length <= 2) return value;
  return `${first}-${second}-${last[0]}${"*".repeat(last.length - 2)}${last.at(-1)}`;
}
