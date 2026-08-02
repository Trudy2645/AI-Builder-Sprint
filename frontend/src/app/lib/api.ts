export type ApiErrorPayload = {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string;
  };
};

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;
  requestId?: string;

  constructor(payload: ApiErrorPayload["error"]) {
    super(payload.message);
    this.name = "ApiError";
    this.code = payload.code;
    this.details = payload.details ?? {};
    this.requestId = payload.request_id;
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const accessTokenKey = "busan-link-access-token";

export function setAccessToken(token: string | null): void {
  if (token) window.localStorage.setItem(accessTokenKey, token);
  else window.localStorage.removeItem(accessTokenKey);
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(accessTokenKey);
}

export function friendlyApiError(error: unknown): string {
  if (error instanceof ApiError) {
    const messages: Record<string, string> = {
      AUTH_REQUIRED: "로그인이 필요합니다. 로그인한 뒤 다시 시도해 주세요.",
      ORGANIZATION_HEADER_REQUIRED: "셀러 조직 정보를 찾을 수 없습니다. 다시 로그인해 주세요.",
      ORG_ACCESS_DENIED: "이 셀러 조직의 공고를 변경할 권한이 없습니다.",
      LISTING_NOT_FOUND: "요청한 공고를 찾을 수 없거나 더 이상 공개되지 않았습니다.",
      LISTING_NOT_AVAILABLE: "이 공고는 현재 계약을 받을 수 없습니다. 다른 공고를 선택해 주세요.",
      SERVICE_PERIOD_UNAVAILABLE: "선택한 이용 기간에는 이 상품을 이용할 수 없습니다.",
      PEOPLE_OUT_OF_RANGE: "입력한 인원이 상품의 허용 인원 범위를 벗어났습니다.",
      QUANTITY_REQUIRED: "객실·차량 등 필요한 수량을 입력해 주세요.",
      UNSUPPORTED_DISPLAY_CURRENCY: "현재는 상품 기준 통화로만 예상 금액을 계산할 수 있습니다.",
      DATABASE_UNAVAILABLE: "서비스 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      AI_INPUT_INSUFFICIENT: "AI 작업에 필요한 계약 조건이 부족합니다. 필수 항목을 확인해 주세요.",
      AI_PROVIDER_TIMEOUT: "AI 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
      AI_PROVIDER_RATE_LIMITED: "AI 요청이 많습니다. 잠시 후 다시 시도해 주세요.",
      AI_PROVIDER_TEMPORARY_FAILURE: "AI 서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해 주세요.",
      AI_SCHEMA_INVALID: "AI가 문서를 올바른 형식으로 분석하지 못했습니다. 내용을 확인한 뒤 다시 시도해 주세요.",
      VERSION_CONFLICT: "다른 곳에서 공고가 변경되었습니다. 목록을 새로고침한 뒤 다시 시도해 주세요.",
      STORAGE_PROVIDER_UNAVAILABLE: "파일 저장소에 연결하지 못했습니다. 서버 설정을 확인해 주세요.",
    };
    return messages[error.code] ?? error.message;
  }
  if (error instanceof TypeError) {
    return "서버에 연결하지 못했습니다. 인터넷 연결과 서버 실행 상태를 확인해 주세요.";
  }
  return "처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.";
}

export async function apiFetch<Data>(path: string, init: RequestInit = {}): Promise<Data> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}),
      ...init.headers,
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.error) {
    throw new ApiError(payload?.error ?? {
      code: "NETWORK_ERROR",
      message: `The server returned ${response.status}.`,
    });
  }
  return payload.data as Data;
}

export type Role = "buyer" | "seller";

type AuthSession = { access_token: string; refresh_token: string; token_type: string; expires_in: number };
export type AuthResponse = { user_id: string; email: string; role?: Role; organization_id?: string | null; session: AuthSession | null };

export function loginWithPassword(email: string, password: string): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function loginDemo(role: Role): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/demo-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
}

export type MeProfile = {
  id: string;
  email: string | null;
  display_name: string;
  affiliation_name: string | null;
  role: Role;
  organizations: Array<{ id: string; name: string; verification_status: string; member_role: string }>;
};

export function getMe(): Promise<MeProfile> {
  return apiFetch<MeProfile>("/me");
}

export function signup(payload: Record<string, unknown>): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export type ContractListItem = {
  id: string;
  listing_title: string;
  seller_name: string;
  status: "draft" | "seller_review" | "revision_requested" | "signing" | "signed" | "cancelled";
  service_start_date: string;
  service_end_date: string;
  requested_people: number;
  amount_minor: number | null;
  currency: string | null;
  created_at: string;
};

export function getMyContracts(): Promise<ContractListItem[]> {
  return apiFetch<ContractListItem[]>("/me/contracts");
}

export type ContractDetail = {
  id: string;
  listing_title: string;
  status: string;
  parties: Array<{ role: "buyer" | "seller"; name: string }>;
  current_version: { id: string; version_no: number; title: string; body: string };
};

export type ApprovalStatus = {
  contract_id: string;
  contract_version_id: string;
  buyer: { approved: boolean };
  seller: { approved: boolean };
  all_approved: boolean;
  contract_status?: string;
};

export function getContractDetail(contractId: string): Promise<ContractDetail> {
  return apiFetch<ContractDetail>(`/contracts/${contractId}`);
}

export function getContractApprovals(contractId: string, versionId: string): Promise<ApprovalStatus> {
  return apiFetch<ApprovalStatus>(`/contracts/${contractId}/versions/${versionId}/approvals`);
}

export function approveContractVersion(contractId: string, versionId: string): Promise<ApprovalStatus> {
  return apiFetch<ApprovalStatus>(`/contracts/${contractId}/versions/${versionId}/approve`, { method: "POST" });
}

export type SignatureRequest = {
  id: string;
  contract_id: string;
  contract_version_id: string;
  status: "preparing" | "in_progress" | "completed" | "failed" | "cancelled";
  provider_document_id: string | null;
  provider_status: string | null;
  current_signing_order: number | null;
  completed_at: string | null;
};

export function getSignatureRequest(id: string): Promise<SignatureRequest> {
  return apiFetch<SignatureRequest>(`/signature-requests/${id}`);
}

export function syncSignatureRequest(id: string): Promise<SignatureRequest> {
  return apiFetch<SignatureRequest>(`/signature-requests/${id}/sync`, { method: "POST" });
}

export type SignatureParticipant = { name: string; email: string };

export function createSignatureRequest(
  contractId: string,
  versionId: string,
  payload: { title: string; buyer: SignatureParticipant; seller: SignatureParticipant },
): Promise<SignatureRequest> {
  return apiFetch<SignatureRequest>(`/contracts/${contractId}/versions/${versionId}/signature-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(payload),
  });
}

export async function downloadModusignFile(documentId: string, kind: "signed" | "audit-trail"): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/modusign/documents/${documentId}/${kind === "signed" ? "download" : "audit-trail"}`, {
    headers: getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {},
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.error ?? { code: "DOWNLOAD_FAILED", message: "파일을 내려받지 못했습니다." });
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${documentId}-${kind}.pdf`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export type PublicListing = {
  id: string;
  seller: { name: string; rating: number; rating_count: number; verified: boolean };
  title: string;
  district: string;
  category: "vehicle_rental" | "activity" | "tour" | "accommodation";
  hero_image_url: string | null;
  ai_summary: string | null;
  base_price: { amount_minor: number; currency: string; unit: string | null } | null;
  availability: { start_date: string | null; end_date: string | null };
  contract_available: boolean;
  attention_required_count?: number;
};

export function getPublicListings(): Promise<PublicListing[]> {
  return apiFetch<PublicListing[]>("/public/listings");
}

export type PublicClause = {
  id: string;
  clause_key: string | null;
  title: string;
  body: string;
  highlight: "critical" | "warning" | "info" | null;
};

export type PublicFinding = {
  id: string | null;
  clause_id: string | null;
  severity: "high" | "medium" | "low" | "none";
  explanation: string;
  suggested_text: string | null;
  disclaimer: string;
};

export type PublicListingDetail = PublicListing & {
  supply_quantity: number | null;
  supply_quantity_description: string | null;
  quantity_unit: string | null;
  minimum_quantity: number | null;
  maximum_quantity: number | null;
  people_per_unit: number | null;
  minimum_people: number | null;
  maximum_people: number | null;
  cancellation_policy: string | null;
  no_show_policy: string | null;
  refund_policy: string | null;
  settlement_policy: string | null;
  safety_policy: string | null;
  compensation_policy: string | null;
  liability_policy: string | null;
  termination_policy: string | null;
  special_terms: string | null;
  clauses: PublicClause[];
};

export type PublicContractPreview = {
  listing_version_id: string;
  body: string;
  clauses: PublicClause[];
  findings: PublicFinding[];
  content_locale: string;
  fallback_locale: string | null;
  localized_content?: {
    locale: string;
    title: string;
    clauses: Array<{ clause_id: string; clause_no: number; title: string; body: string; easy_explanation: string }>;
    findings: Array<{ finding_id: string; clause_id: string | null; severity: PublicFinding["severity"]; explanation: string; suggested_text: string | null; disclaimer: string }>;
  } | null;
};

export function getPublicListingDetail(listingId: string, locale = "ko-KR"): Promise<PublicListingDetail> {
  return apiFetch<PublicListingDetail>(`/public/listings/${listingId}?locale=${encodeURIComponent(locale)}`);
}

export function getPublicContractPreview(listingId: string, locale = "ko-KR"): Promise<PublicContractPreview> {
  return apiFetch<PublicContractPreview>(`/public/listings/${listingId}/contract-preview?locale=${encodeURIComponent(locale)}`);
}

export type RevisionGuidance = { id: string; impact: string; recommendation: string };

export function generateRevisionGuidance(items: Array<{
  id: string;
  clause_title: string;
  original_text: string;
  requested_text: string;
  reason: string;
}>): Promise<{ items: RevisionGuidance[] }> {
  return apiFetch<{ items: RevisionGuidance[] }>("/ai-guidance/revision-impact", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ items }),
  });
}

export function generateChangeSummary(changes: Array<{ title: string; before?: string; after?: string }>): Promise<{ lines: string[] }> {
  return apiFetch<{ lines: string[] }>("/ai-guidance/change-summary", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ changes }),
  });
}
