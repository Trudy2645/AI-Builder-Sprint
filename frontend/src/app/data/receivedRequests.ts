export interface ReceivedRevision {
  id: string;
  clauseNo: string;
  clauseTitle: string;
  original: string;
  requested: string;
  reason: string;
  aiImpact: string;
  aiRecommend: string;
}

export interface ReceivedRequest {
  id: string;
  buyer: string;
  contractId: string;
  contractTitle: string;
  status: "new" | "negotiating" | "signing" | "signed";
  createdAt: string;
  period: string;
  estimatedAmount: string;
  currentVersion: string;
  revisions: ReceivedRevision[];
}

// 받은 요청은 백엔드 계약 요청 API에서만 제공한다.
export const receivedRequests: ReceivedRequest[] = [];

export function getReceivedRequest(id: string | undefined): ReceivedRequest | undefined {
  return receivedRequests.find((request) => request.id === id);
}
