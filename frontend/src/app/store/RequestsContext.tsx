import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type RequestStatus =
  | "draft"
  | "reviewing"
  | "responded"
  | "negotiating"
  | "signing"
  | "completed"
  | "closed";

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
}

interface RequestsContextValue {
  requests: SentRequest[];
  addRequest: (r: Omit<SentRequest, "id" | "createdAt">) => string;
  updateRequestStatus: (
    id: string,
    status: RequestStatus,
    patch?: Partial<SentRequest>,
  ) => void;
}

const RequestsContext = createContext<RequestsContextValue | null>(null);

export function RequestsProvider({ children }: { children: ReactNode }) {
  const [requests, setRequests] = useState<SentRequest[]>([]);

  const addRequest: RequestsContextValue["addRequest"] = (r) => {
    const now = new Date();
    const createdAt = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}`;
    const id = `req-${Date.now()}`;
    setRequests((prev) => [{ ...r, id, createdAt }, ...prev]);
    return id;
  };

  const updateRequestStatus: RequestsContextValue["updateRequestStatus"] = (
    id,
    status,
    patch,
  ) => {
    setRequests((prev) =>
      prev.map((request) =>
        request.id === id ? { ...request, ...patch, status } : request,
      ),
    );
  };

  const value = useMemo(
    () => ({ requests, addRequest, updateRequestStatus }),
    [requests],
  );

  return <RequestsContext.Provider value={value}>{children}</RequestsContext.Provider>;
}

export function useRequests() {
  const ctx = useContext(RequestsContext);
  if (!ctx) throw new Error("useRequests must be used within RequestsProvider");
  return ctx;
}
