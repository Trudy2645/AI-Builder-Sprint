import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import { getAccessToken, getMyContracts } from "../lib/api";

export type BuyerContractStatus =
  | "draft"
  | "seller_review"
  | "revision_requested"
  | "signing"
  | "signed"
  | "cancelled";

export interface BuyerContractDraft {
  title: string;
  buyerName: string;
  sellerName: string;
  category: string;
  startDate: string;
  endDate: string;
  peopleCount: number;
  quantity: number;
  unitPrice: number;
  cancellationPolicy: string;
  settlementPolicy: string;
}

export interface BuyerContract extends BuyerContractDraft {
  id: string;
  status: BuyerContractStatus;
  source: "upload" | "write";
  createdAt: string;
}

interface BuyerContractsContextValue {
  contracts: BuyerContract[];
  latestContract?: BuyerContract;
  createContractRequest: (
    draft: BuyerContractDraft,
    source: BuyerContract["source"],
  ) => BuyerContract;
}

const BuyerContractsContext = createContext<BuyerContractsContextValue | null>(null);

export const DEFAULT_BUYER_CONTRACT_DRAFT: BuyerContractDraft = {
  title: "해운대 오션스테이 여름 객실 공급",
  buyerName: "GlobalTrip Japan",
  sellerName: "해운대 오션스테이",
  category: "숙박",
  startDate: "2026-07-01",
  endDate: "2026-08-31",
  peopleCount: 30,
  quantity: 30,
  unitPrice: 145000,
  cancellationPolicy: "체크인 7일 전까지 무료 취소",
  settlementPolicy: "월 마감 후 15일 이내",
};

function todayIso() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate(),
  ).padStart(2, "0")}`;
}

function nextId(count: number) {
  return `BL-2026-${String(count + 1).padStart(3, "0")}`;
}

export function BuyerContractsProvider({ children }: { children: ReactNode }) {
  const { isDemoSession } = useApp();
  const [contracts, setContracts] = useState<BuyerContract[]>([]);

  useEffect(() => {
    if (isDemoSession) {
      setContracts([]);
      return;
    }
    if (!getAccessToken()) {
      setContracts([]);
      return;
    }
    let active = true;
    getMyContracts()
      .then((items) => {
        if (!active) return;
        setContracts(items.map((item) => ({
          id: item.id,
          title: item.listing_title,
          buyerName: "",
          sellerName: item.seller_name,
          category: "",
          startDate: item.service_start_date,
          endDate: item.service_end_date,
          peopleCount: item.requested_people,
          quantity: 0,
          unitPrice: item.amount_minor ?? 0,
          cancellationPolicy: "",
          settlementPolicy: "",
          status: item.status,
          source: "write",
          createdAt: item.created_at,
        })));
      })
      .catch(() => {
        if (active) setContracts([]);
      });
    return () => { active = false; };
  }, [isDemoSession]);

  const createContractRequest: BuyerContractsContextValue["createContractRequest"] = (
    draft,
    source,
  ) => {
    const contract: BuyerContract = {
      ...draft,
      id: nextId(contracts.length),
      status: "seller_review",
      source,
      createdAt: todayIso(),
    };
    setContracts((prev) => [contract, ...prev]);
    return contract;
  };

  const value = useMemo(
    () => ({
      contracts,
      latestContract: contracts[0],
      createContractRequest,
    }),
    [contracts],
  );

  return (
    <BuyerContractsContext.Provider value={value}>{children}</BuyerContractsContext.Provider>
  );
}

export function useBuyerContracts() {
  const ctx = useContext(BuyerContractsContext);
  if (!ctx) throw new Error("useBuyerContracts must be used within BuyerContractsProvider");
  return ctx;
}
