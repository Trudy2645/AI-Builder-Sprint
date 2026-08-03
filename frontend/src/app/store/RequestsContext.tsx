import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import {
  getBuyerRevisionRequests,
  getMyContracts,
  getReceivedContracts,
  getSellerRevisionRequests,
  type ContractListItem,
  type SellerContractListItem,
  type SellerRevisionRequestListItem,
} from "../lib/api";

export type RequestStatus = "draft" | "reviewing" | "final_review" | "responded" | "negotiating" | "signing" | "completed" | "closed";
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
  revisionRequestId?: string;
  revisionStatus?: SellerRevisionRequestListItem["status"];
  revisionItemCount?: number;
}

function requestStatus(
  status: string,
  revisionStatus?: SellerRevisionRequestListItem["status"],
  sellerApproved = false,
): RequestStatus {
  if (revisionStatus && ["countered", "partially_accepted"].includes(revisionStatus)) {
    return "responded";
  }
  if (revisionStatus === "rejected") {
    return "responded";
  }
  switch (status) {
    case "seller_review": return sellerApproved ? "final_review" : "reviewing";
    case "revision_requested": return "negotiating";
    case "signing": return "signing";
    case "signed": return "completed";
    case "cancelled": return "closed";
    default: return "draft";
  }
}

function fromBuyerContract(
  item: ContractListItem,
  revision?: SellerRevisionRequestListItem,
): SentRequest {
  return {
    id: item.id,
    contractId: item.id,
    seller: item.seller_name,
    title: item.listing_title,
    type: item.initial_request_kind === "revision" ? "revision" : "asis",
    status: requestStatus(item.status, revision?.status, item.seller_approved),
    createdAt: item.created_at.slice(0, 10).replace(/-/g, "."),
    guests: item.requested_people,
    total: item.amount_minor ?? undefined,
    currency: item.currency ?? undefined,
    serviceStartDate: item.service_start_date,
    serviceEndDate: item.service_end_date,
    revisionRequestId: revision?.id,
    revisionStatus: revision?.status,
    revisionItemCount: revision?.item_count,
  };
}

function fromSellerContract(
  item: SellerContractListItem,
  revision?: SellerRevisionRequestListItem,
): SentRequest {
  return {
    id: item.contract_id,
    contractId: item.contract_id,
    seller: "",
    buyer: item.buyer_name,
    title: item.listing_title,
    type: item.initial_request_kind === "revision" ? "revision" : "asis",
    status: item.status === "revision_requested" ? "negotiating" : requestStatus(item.status),
    createdAt: item.requested_at.slice(0, 10).replace(/-/g, "."),
    guests: item.requested_people,
    total: item.amount_minor ?? undefined,
    currency: item.currency ?? undefined,
    serviceStartDate: item.service_start_date,
    serviceEndDate: item.service_end_date,
    revisionRequestId: revision?.id,
    revisionStatus: revision?.status,
    revisionItemCount: revision?.item_count,
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
      if (currentRole === "buyer") {
        const [items, revisions] = await Promise.all([
          getMyContracts(),
          getBuyerRevisionRequests().catch(() => []),
        ]);
        const revisionByContract = new Map<string, SellerRevisionRequestListItem>();
        for (const revision of revisions) {
          const previous = revisionByContract.get(revision.contract_id);
          if (!previous || revision.updated_at > previous.updated_at) {
            revisionByContract.set(revision.contract_id, revision);
          }
        }
        setRequests(items.map((item) => fromBuyerContract(item, revisionByContract.get(item.id))));
      } else {
        const [items, revisions] = await Promise.all([
          getReceivedContracts(),
          getSellerRevisionRequests().catch(() => []),
        ]);
        const revisionByContract = new Map<string, SellerRevisionRequestListItem>();
        for (const revision of revisions) {
          const previous = revisionByContract.get(revision.contract_id);
          if (!previous || revision.updated_at > previous.updated_at) {
            revisionByContract.set(revision.contract_id, revision);
          }
        }
        setRequests(items.map((item) => fromSellerContract(item, revisionByContract.get(item.contract_id))));
      }
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
