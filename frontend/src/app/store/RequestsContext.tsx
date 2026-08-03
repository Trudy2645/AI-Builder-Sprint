import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import { getMyContracts, getReceivedContracts, type ContractListItem, type SellerContractListItem } from "../lib/api";

export type RequestStatus = "draft" | "reviewing" | "responded" | "negotiating" | "signing" | "completed" | "closed";
export type RequestType = "asis" | "revision";

export interface RevisionItem {
  id: string;
  clauseNo: string;
  clauseTitle: string;
  original: string;
  changeType: string;
  requested: string;
  reason: string;
  attachment?: string;
  sellerDecision?: "accept" | "reject" | "counter";
  sellerResponse?: string;
}

export interface SentRequest {
  id: string;
  contractId: string;
  seller: string;
  buyer?: string;
  title: string;
  type: RequestType;
  status: RequestStatus;
  createdAt: string;
  guests?: number;
  rooms?: number;
  total?: number;
  currency?: string;
  message?: string;
  revisions?: RevisionItem[];
  currentVersion?: "v1" | "v2" | "v3" | "v4";
  latestResponse?: string;
  serviceStartDate?: string;
  serviceEndDate?: string;
}

function requestStatus(status: string): RequestStatus {
  switch (status) {
    case "seller_review": return "reviewing";
    case "revision_requested": return "negotiating";
    case "signing": return "signing";
    case "signed": return "completed";
    case "cancelled": return "closed";
    default: return "draft";
  }
}

function fromBuyerContract(item: ContractListItem): SentRequest {
  return {
    id: item.id,
    contractId: item.id,
    seller: item.seller_name,
    title: item.listing_title,
    type: item.initial_request_kind === "revision" ? "revision" : "asis",
    status: requestStatus(item.status),
    createdAt: item.created_at.slice(0, 10).replace(/-/g, "."),
    guests: item.requested_people,
    total: item.amount_minor ?? undefined,
    currency: item.currency ?? undefined,
    serviceStartDate: item.service_start_date,
    serviceEndDate: item.service_end_date,
  };
}

function fromSellerContract(item: SellerContractListItem): SentRequest {
  return {
    id: item.contract_id,
    contractId: item.contract_id,
    seller: "",
    buyer: item.buyer_name,
    title: item.listing_title,
    type: item.initial_request_kind === "revision" ? "revision" : "asis",
    status: requestStatus(item.status),
    createdAt: item.requested_at.slice(0, 10).replace(/-/g, "."),
    guests: item.requested_people,
    total: item.amount_minor ?? undefined,
    currency: item.currency ?? undefined,
    serviceStartDate: item.service_start_date,
    serviceEndDate: item.service_end_date,
  };
}

interface RequestsContextValue {
  requests: SentRequest[];
  loading: boolean;
  refreshRequests: () => Promise<void>;
  /** Kept for callers that only need to refresh after a successful API mutation. */
  updateRequestStatus: (_id: string, _status: RequestStatus, _patch?: Partial<SentRequest>) => void;
}

const RequestsContext = createContext<RequestsContextValue | null>(null);

export function RequestsProvider({ children }: { children: ReactNode }) {
  const { currentRole } = useApp();
  const [requests, setRequests] = useState<SentRequest[]>([]);
  const [loading, setLoading] = useState(false);

  const refreshRequests = useCallback(async () => {
    if (!currentRole) {
      setRequests([]);
      return;
    }
    setLoading(true);
    try {
      const items = currentRole === "buyer" ? await getMyContracts() : await getReceivedContracts();
      setRequests(currentRole === "buyer" ? items.map(fromBuyerContract) : items.map(fromSellerContract));
    } finally {
      setLoading(false);
    }
  }, [currentRole]);

  useEffect(() => {
    void refreshRequests().catch(() => setRequests([]));
  }, [refreshRequests]);

  const updateRequestStatus = useCallback(() => {
    void refreshRequests();
  }, [refreshRequests]);

  const value = useMemo(() => ({ requests, loading, refreshRequests, updateRequestStatus }), [requests, loading, refreshRequests, updateRequestStatus]);
  return <RequestsContext.Provider value={value}>{children}</RequestsContext.Provider>;
}

export function useRequests() {
  const context = useContext(RequestsContext);
  if (!context) throw new Error("useRequests must be used within RequestsProvider");
  return context;
}
