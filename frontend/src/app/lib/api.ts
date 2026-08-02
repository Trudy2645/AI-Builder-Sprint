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
const accessTokenKey = "busanlink.access_token";

export function setAccessToken(token: string | null): void {
  if (token) window.localStorage.setItem(accessTokenKey, token);
  else window.localStorage.removeItem(accessTokenKey);
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(accessTokenKey);
}

type ApiSession = {
  accessToken: string;
  organizationId: string;
};

let activeSession: ApiSession | null = null;

type UploadedDocumentProcessingResult = {
  listingId: string;
  sourceDocumentId: string;
  listingVersionNo: number;
  listingCandidate: {
    title?: string;
    category?: "vehicle_rental" | "activity" | "tour" | "accommodation";
    terms?: Record<string, unknown>;
  } | null;
  confirmationRequired: string[];
  validationWarnings: string[];
  extraction: Record<string, unknown> | null;
};

function requestIdempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function getApiSession(): ApiSession {
  if (activeSession) return activeSession;
  const accessToken = window.localStorage.getItem("busanlink.access_token")
    ?? import.meta.env.VITE_API_ACCESS_TOKEN;
  const organizationId = window.localStorage.getItem("busanlink.organization_id")
    ?? import.meta.env.VITE_SELLER_ORGANIZATION_ID;
  if (!accessToken || !organizationId) {
    throw new Error("API 로그인 정보가 없습니다. 로그인 후 다시 시도해 주세요.");
  }
  return { accessToken, organizationId };
}

function authenticatedHeaders(session: ApiSession, headers: HeadersInit = {}): Headers {
  const result = new Headers(headers);
  result.set("Authorization", `Bearer ${session.accessToken}`);
  result.set("X-Organization-Id", session.organizationId);
  return result;
}

export function friendlyApiError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "VALIDATION_ERROR" || error.code === "REQUEST_VALIDATION_FAILED") {
      const errors = Array.isArray(error.details.errors) ? error.details.errors : [];
      const fieldLabels: Record<string, string> = {
        people: "여행 인원",
        quantity: "수량",
        quantity_unit: "수량 단위",
        nights: "숙박 일수",
        start_date: "이용 시작일",
        end_date: "이용 종료일",
        currency: "통화",
        request_message: "요청 내용",
        group_name: "그룹명",
      };
      const translated = errors.map((entry) => {
        const item = entry as { location?: string; message?: string };
        const location = item.location?.split(".").pop() ?? "입력값";
        const label = fieldLabels[location] ?? location;
        const message = item.message ?? "값을 확인해 주세요.";
        if (message.includes("end_date must be later than start_date")) return "이용 종료일은 시작일보다 늦어야 합니다.";
        if (message.includes("nights must equal")) return "숙박 일수는 시작일과 종료일 사이의 실제 일수와 같아야 합니다.";
        if (message.includes("group_name is required")) return "단체 대표 서명은 그룹명을 입력해야 합니다.";
        if (message.includes("Field required")) return `${label}을(를) 입력해 주세요.`;
        if (message.includes("greater than 0")) return `${label}은(는) 1 이상이어야 합니다.`;
        if (message.includes("valid date")) return `${label}을(를) 올바른 날짜로 입력해 주세요.`;
        return `${label}: ${message}`;
      });
      if (translated.length > 0) return `입력값을 확인해 주세요.\n${translated.join("\n")}`;
      return "입력값을 확인해 주세요. 필수 항목과 날짜·수량을 다시 확인한 뒤 재시도해 주세요.";
    }
    const messages: Record<string, string> = {
      AUTH_REQUIRED: "로그인이 필요합니다. 로그인한 뒤 다시 시도해 주세요.",
      LISTING_NOT_FOUND: "요청한 공고를 찾을 수 없거나 더 이상 공개되지 않았습니다.",
      LISTING_NOT_AVAILABLE: "이 공고는 현재 계약을 받을 수 없습니다. 다른 공고를 선택해 주세요.",
      SERVICE_PERIOD_UNAVAILABLE: "선택한 이용 기간에는 이 상품을 이용할 수 없습니다.",
      PEOPLE_OUT_OF_RANGE: "입력한 인원이 상품의 허용 인원 범위를 벗어났습니다.",
      QUANTITY_REQUIRED: "객실·차량 등 필요한 수량을 입력해 주세요.",
      UNSUPPORTED_QUANTITY_UNIT: "이 공고의 과금 단위와 맞지 않습니다. 공고 상세의 단위를 확인해 주세요.",
      INVALID_BILLING_QUANTITY: "인원수와 과금 수량이 일치해야 합니다.",
      LISTING_EXPIRED: "이 공고의 계약 가능 기간이 끝났습니다. 다른 공고를 선택해 주세요.",
      EXCHANGE_RATE_UNAVAILABLE: "환율 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      IDEMPOTENCY_CONFLICT: "같은 요청이 이미 처리 중이거나 처리되었습니다. 잠시 후 목록을 새로고침해 주세요.",
      IDEMPOTENCY_KEY_REUSED: "이미 사용한 요청 키입니다. 화면을 새로고침한 뒤 다시 시도해 주세요.",
      CONTRACT_ACCESS_DENIED: "이 계약을 볼 권한이 없습니다.",
      INVALID_STATE_TRANSITION: "현재 계약 상태에서는 이 작업을 진행할 수 없습니다.",
      ORGANIZATION_HEADER_REQUIRED: "셀러 조직 정보가 없어 요청할 수 없습니다. 다시 로그인해 주세요.",
      UNSUPPORTED_DISPLAY_CURRENCY: "현재는 상품 기준 통화로만 예상 금액을 계산할 수 있습니다.",
      DATABASE_UNAVAILABLE: "서비스 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    };
    return messages[error.code] ?? error.message;
  }
  if (error instanceof TypeError) {
    return "서버에 연결하지 못했습니다. 인터넷 연결과 서버 실행 상태를 확인해 주세요.";
  }
  return "처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.";
}

export async function apiFetch<Data>(path: string, init: RequestInit = {}): Promise<Data> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
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

/**
 * Creates a draft listing, uploads a contract, waits for the backend's AI workflow,
 * and returns only the structured candidate intended for seller confirmation.
 */
export type ContractProcessingStage = "uploading" | "ocr" | "extracting" | "matching" | "finalizing";

export async function uploadAndProcessSourceContract(
  file: File,
  onStage?: (stage: ContractProcessingStage) => void,
): Promise<UploadedDocumentProcessingResult> {
  const session = getApiSession();
  onStage?.("uploading");
  const sha256 = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const contentSha256 = Array.from(new Uint8Array(sha256))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  const headers = authenticatedHeaders(session, { "Content-Type": "application/json" });

  const listing = await apiFetch<{ listing_id: string }>("/seller/listings", {
    method: "POST",
    headers: new Headers([
      ...headers.entries(),
      ["Idempotency-Key", requestIdempotencyKey("listing-create")],
    ]),
    body: JSON.stringify({
      creation_method: "upload",
      title: file.name.replace(/\.[^.]+$/, "") || "업로드 계약서",
      category: "accommodation",
      district: "부산",
      language: "ko-KR",
    }),
  });

  const upload = await apiFetch<{ document: { id: string }; upload_url: string; method: string }>("/documents/upload-url", {
    method: "POST",
    headers: new Headers([
      ...headers.entries(),
      ["Idempotency-Key", requestIdempotencyKey("document-upload")],
    ]),
    body: JSON.stringify({
      listing_id: listing.listing_id,
      purpose: "source_contract",
      original_filename: file.name,
      mime_type: file.type || "application/pdf",
      size_bytes: file.size,
      content_sha256: contentSha256,
    }),
  });

  const putResponse = await fetch(upload.upload_url, {
    method: upload.method,
    headers: { "Content-Type": file.type || "application/pdf" },
    body: file,
  });
  if (!putResponse.ok) throw new Error("계약서 파일을 저장하지 못했습니다.");

  await apiFetch(`/documents/${upload.document.id}/complete`, {
    method: "POST",
    headers: authenticatedHeaders(session),
  });
  await apiFetch(`/documents/${upload.document.id}/process`, {
    method: "POST",
    headers: new Headers([
      ...authenticatedHeaders(session).entries(),
      ["Idempotency-Key", requestIdempotencyKey("document-process")],
    ]),
  });
  onStage?.("ocr");

  for (let attempt = 0; attempt < 30; attempt += 1) {
    const result = await apiFetch<{
      status: "processing" | "ready" | "failed";
      listing_candidate: UploadedDocumentProcessingResult["listingCandidate"];
      extraction: Record<string, unknown> | null;
      confirmation_required: string[];
      validation_warnings: string[];
      failure_code: string | null;
    }>(`/documents/${upload.document.id}/processing-result`, {
      headers: authenticatedHeaders(session),
    });
    if (result.status === "ready") {
      onStage?.("finalizing");
      return {
        listingId: listing.listing_id,
        sourceDocumentId: upload.document.id,
        listingVersionNo: listing.version_no,
        listingCandidate: result.listing_candidate,
        confirmationRequired: result.confirmation_required,
        validationWarnings: result.validation_warnings,
        extraction: result.extraction,
      };
    }
    onStage?.(attempt < 8 ? "extracting" : "matching");
    if (result.status === "failed") throw new Error(`AI 계약서 분석에 실패했습니다${result.failure_code ? ` (${result.failure_code})` : ""}.`);
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
  throw new Error("AI 분석 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.");
}

export async function publishSellerListing(listingId: string): Promise<void> {
  const session = getApiSession();
  await apiFetch(`/seller/listings/${listingId}/complete`, { method: "POST", headers: authenticatedHeaders(session) });
  await apiFetch(`/seller/listings/${listingId}/publish`, { method: "POST", headers: authenticatedHeaders(session) });
}

export type SellerListingSummary = {
  id: string;
  title: string;
  category: "vehicle_rental" | "activity" | "tour" | "accommodation";
  district: string;
  status: "draft" | "processing" | "ready" | "published" | "paused" | "expired" | "archived";
  creation_method: "manual" | "upload";
  service_start_date: string | null;
  service_end_date: string | null;
  supply_quantity_description: string | null;
  base_price: { amount_minor: number; currency: string; unit: string | null } | null;
  contract_request_count: number;
  attention_required_count: number;
  updated_at: string;
};

export function getSellerListings(): Promise<SellerListingSummary[]> {
  const session = getApiSession();
  return apiFetch<SellerListingSummary[]>("/seller/listings", { headers: authenticatedHeaders(session) });
}

export async function changeSellerListingStatus(listingId: string, action: "publish" | "pause" | "archive"): Promise<void> {
  const session = getApiSession();
  await apiFetch(`/seller/listings/${listingId}/${action}`, { method: "POST", headers: authenticatedHeaders(session) });
}

function apiPriceUnit(label: string): { priceUnit: string; quantityUnit: string } {
  if (label.includes("좌석")) return { priceUnit: "seat", quantityUnit: "seat" };
  if (label.includes("차량") || label.includes("동")) return { priceUnit: "vehicle", quantityUnit: "vehicle" };
  if (label.includes("인")) return { priceUnit: "person", quantityUnit: "person" };
  return { priceUnit: "room_night", quantityUnit: "room" };
}

/** Persist the reviewed seller input before exposing it to buyers. */
export async function registerPublishedSellerListing(input: {
  listingId?: string;
  baseVersionNo?: number;
  sourceDocumentId?: string;
  method: "write" | "upload";
  productName: string;
  category: "vehicle_rental" | "activity" | "tour" | "accommodation";
  district: string;
  availabilityStart: string;
  availabilityEnd: string;
  quantity: string;
  unitPrice: string;
  priceUnit: string;
  minQty: string;
  maxQty: string;
  cancellation: string;
  noShow: string;
  settlement: string;
  liability: string;
  termination: string;
  special: string;
  headline: string;
}): Promise<SellerListingSummary> {
  const session = getApiSession();
  const headers = authenticatedHeaders(session, { "Content-Type": "application/json" });
  const created = input.listingId
    ? { listing_id: input.listingId, version_no: input.baseVersionNo ?? 1 }
    : await apiFetch<{ listing_id: string; version_no: number }>("/seller/listings", {
      method: "POST",
      headers: new Headers([...headers.entries(), ["Idempotency-Key", requestIdempotencyKey("listing-register")]]),
      body: JSON.stringify({
        creation_method: input.method === "write" ? "manual" : "upload",
        title: input.productName,
        category: input.category,
        district: input.district,
        language: "ko-KR",
      }),
    });
  const units = apiPriceUnit(input.priceUnit);
  const minimumQuantity = Number(input.minQty) || undefined;
  const maximumQuantity = Number(input.maxQty) || undefined;
  await apiFetch(`/seller/listings/${created.listing_id}/terms`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({
      base_version_no: created.version_no,
      terms: {
        service_start_date: input.availabilityStart || undefined,
        service_end_date: input.availabilityEnd || undefined,
        supply_quantity_description: input.quantity,
        quantity_unit: units.quantityUnit,
        minimum_quantity: minimumQuantity,
        maximum_quantity: maximumQuantity,
        base_price_amount_minor: Number(input.unitPrice),
        currency: "KRW",
        price_unit: units.priceUnit,
        cancellation_policy: input.cancellation,
        no_show_policy: input.noShow,
        settlement_policy: input.settlement,
        liability_policy: input.liability,
        termination_policy: input.termination,
        special_terms: input.special || undefined,
      },
    }),
  });
  if (input.headline.trim() || input.sourceDocumentId) {
    await apiFetch(`/seller/listings/${created.listing_id}/presentation`, {
      method: "PATCH", headers,
      body: JSON.stringify({ public_headline: input.headline.trim() || undefined, hero_document_id: input.sourceDocumentId || undefined }),
    });
  }
  await publishSellerListing(created.listing_id);
  const listings = await getSellerListings();
  const listing = listings.find((item) => item.id === created.listing_id);
  if (!listing || listing.status !== "published") throw new Error("공고 공개 상태를 확인하지 못했습니다.");
  return listing;
}

export async function updateSellerListingTerms(listingId: string, terms: Record<string, unknown> = {}): Promise<void> {
  const session = getApiSession();
  const body = {
    base_price_amount_minor: Number(terms.base_price_amount_minor) || 0,
    currency: String(terms.currency || "KRW"),
    price_unit: String(terms.price_unit || "객실당"),
    supply_quantity_description: String(terms.quantity || "공급 수량은 바이어 요청 시 확정"),
    maximum_people: Number(terms.maximum_people) || 12,
    cancellation_policy: String(terms.cancellation_policy || "계약서 기준"),
    refund_policy: String(terms.refund_policy || "계약서 기준"),
    no_show_policy: String(terms.no_show_policy || terms.refund_policy || "계약서 기준"),
    settlement_policy: String(terms.settlement_terms || "양 당사자 협의"),
    liability_policy: String(terms.liability_policy || "계약서 기준"),
    termination_policy: String(terms.termination_policy || "계약서 기준"),
  };
  await apiFetch(`/seller/listings/${listingId}/terms`, { method: "PATCH", headers: authenticatedHeaders(session, { "Content-Type": "application/json" }), body: JSON.stringify({ base_version_no: 1, terms: body }) });
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

export type SellerReceivedContract = {
  contract_id: string; listing_id: string | null; listing_title: string; buyer_name: string;
  requested_people: number; service_start_date: string; service_end_date: string;
  amount_minor: number | null; currency: string | null; initial_request_kind: "as_is" | "revision"; status: string; requested_at: string;
};

export function getSellerReceivedContracts(): Promise<SellerReceivedContract[]> {
  const session = getApiSession();
  return apiFetch<SellerReceivedContract[]>("/seller/contracts/received", { headers: authenticatedHeaders(session) });
}

export type SellerRevisionSummary = { id: string; contract_id: string; listing_title: string; buyer_name: string; status: string; message: string | null; item_count: number; sent_at: string | null; updated_at: string };
export type RevisionDetail = { id: string; contract_id: string; base_version_no: number; status: string; message: string | null; items: Array<{ id: string; item_order: number; request_type: "modify" | "delete" | "add"; clause_id: string | null; reason: string; requested_text: string | null; decision: "pending" | "accepted" | "rejected" | "countered"; seller_reason: string | null; counter_text: string | null }> };

export function getSellerRevisionRequests(): Promise<SellerRevisionSummary[]> {
  const session = getApiSession();
  return apiFetch<SellerRevisionSummary[]>("/seller/revision-requests", { headers: authenticatedHeaders(session) });
}
export function getRevisionRequest(id: string): Promise<RevisionDetail> {
  const session = getApiSession();
  return apiFetch<RevisionDetail>(`/revision-requests/${id}`, { headers: authenticatedHeaders(session) });
}
export function createRevisionRequest(contractId: string, payload: { base_version_no: number; message?: string; items: Array<{ request_type: "modify" | "delete" | "add"; clause_id?: string; reason: string; requested_text?: string }> }): Promise<{ revision_request_id: string; status: string }> {
  const session = getApiSession();
  return apiFetch(`/contracts/${contractId}/revision-requests`, { method: "POST", headers: new Headers([...authenticatedHeaders(session, { "Content-Type": "application/json" }).entries(), ["Idempotency-Key", requestIdempotencyKey("revision-request")]]), body: JSON.stringify(payload) });
}
export function sendRevisionRequest(revisionId: string): Promise<unknown> {
  const session = getApiSession();
  return apiFetch(`/revision-requests/${revisionId}/send`, { method: "POST", headers: new Headers([...authenticatedHeaders(session, { "Content-Type": "application/json" }).entries(), ["Idempotency-Key", requestIdempotencyKey("revision-send")]]) });
}
export type BuyerRevisionSummary = SellerRevisionSummary;
export function getBuyerRevisionRequests(): Promise<BuyerRevisionSummary[]> {
  const token = getAccessToken();
  if (!token) return Promise.resolve([]);
  return apiFetch<BuyerRevisionSummary[]>("/me/revision-requests", { headers: { Authorization: `Bearer ${token}` } });
}
export function markRevisionRequestRead(revisionId: string): Promise<{ read: boolean }> {
  const token = getAccessToken();
  if (!token) return Promise.resolve({ read: false });
  return apiFetch(`/revision-requests/${revisionId}/read`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
}
export function decideRevisionItem(revisionId: string, itemId: string, payload: { decision: "accepted" | "rejected" | "countered"; seller_reason?: string; counter_text?: string }): Promise<RevisionDetail> {
  const session = getApiSession();
  return apiFetch<RevisionDetail>(`/revision-requests/${revisionId}/items/${itemId}`, { method: "PATCH", headers: new Headers([...authenticatedHeaders(session, { "Content-Type": "application/json" }).entries(), ["Idempotency-Key", requestIdempotencyKey("revision-item-decide")]]), body: JSON.stringify(payload) });
}
export function decideRevisionRequest(id: string, sellerMessage?: string): Promise<unknown> {
  const session = getApiSession();
  return apiFetch(`/revision-requests/${id}/decide`, { method: "POST", headers: new Headers([...authenticatedHeaders(session, { "Content-Type": "application/json" }).entries(), ["Idempotency-Key", requestIdempotencyKey("revision-decide")]]), body: JSON.stringify({ seller_message: sellerMessage }) });
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
  seller: { name: string };
  title: string;
  district: string;
  category: "vehicle_rental" | "activity" | "tour" | "accommodation";
  hero_image_url: string | null;
  ai_summary: string | null;
  base_price: { amount_minor: number; currency: string; unit: string | null } | null;
  availability: { start_date: string | null; end_date: string | null };
  contract_available: boolean;
};

export function getPublicListings(): Promise<PublicListing[]> {
  return apiFetch<PublicListing[]>("/public/listings");
}

export type PublicListingDetail = PublicListing & {
  supply_quantity_description: string | null;
  cancellation_policy: string | null;
  no_show_policy: string | null;
  settlement_policy: string | null;
  quantity_unit: string | null;
  clauses: Array<{ id: string; clause_order?: number; title: string; body: string }>;
};

export function getPublicListing(listingId: string): Promise<PublicListingDetail> {
  return apiFetch<PublicListingDetail>(`/public/listings/${listingId}`);
}

export function getPublicSourceDocumentUrl(listingId: string): Promise<{ document_id: string; download_url: string; expires_at: string }> {
  const token = getAccessToken();
  if (!token) throw new ApiError({ code: "AUTH_REQUIRED", message: "Login required." });
  return apiFetch(`/public/listings/${listingId}/source-document-url`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getPublicListingAsContract(listingId: string): Promise<import("../data/contracts").Contract> {
  const listing = await getPublicListing(listingId);
  return {
    id: listing.id, seller: listing.seller.name, title: listing.title, category: listing.category,
    district: listing.district, start: listing.availability.start_date ?? "미정", end: listing.availability.end_date ?? "미정",
    unitPrice: listing.base_price?.amount_minor ?? 0, priceUnit: listing.base_price?.unit ?? "기준 단가", quantityUnit: listing.quantity_unit ?? undefined,
    quantityLabel: listing.supply_quantity_description ?? "미정", capacity: Number.MAX_SAFE_INTEGER,
    available: listing.contract_available, popularity: 0, createdOrder: 0, recommendScore: 0,
    image: listing.hero_image_url ?? "", aiSummary: listing.ai_summary?.split("\n") ?? ["AI 요약이 아직 준비되지 않았습니다."],
    details: {
      period: `${listing.availability.start_date ?? "미정"} ~ ${listing.availability.end_date ?? "미정"}`,
      supplyQuantity: listing.supply_quantity_description ?? "미정",
      unitPrice: `${(listing.base_price?.amount_minor ?? 0).toLocaleString("ko-KR")} ${listing.base_price?.currency ?? "KRW"}`,
      cancellation: listing.cancellation_policy ?? "미정", noShow: listing.no_show_policy ?? "미정", settlement: listing.settlement_policy ?? "미정",
    },
    clauses: listing.clauses.map((clause, index) => ({ id: clause.id, no: `제${index + 1}조`, title: clause.title, text: clause.body })),
  };
}

export function createPublicContractRequest(listingId: string, payload: {
  people: number; quantity: number; quantity_unit: string; nights: number;
  start_date: string; end_date: string; currency: string; request_message?: string;
  initial_request_kind: "as_is" | "revision";
}): Promise<{ contract_id: string; version_no: number; status: string }> {
  const session = getApiSession();
  return apiFetch(`/listings/${listingId}/contract-requests`, {
    method: "POST",
    headers: new Headers([...authenticatedHeaders(session, { "Content-Type": "application/json" }).entries(), ["Idempotency-Key", requestIdempotencyKey("contract-request")]]),
    body: JSON.stringify({ signing_capacity: "self", ...payload }),
  });
}

export type AuthenticatedDemoSession = {
  accessToken: string;
  refreshToken: string;
  email: string;
  organizationId?: string;
};

export async function loginWithDemoRole(role: "buyer" | "seller"): Promise<AuthenticatedDemoSession> {
  const result = await apiFetch<{
    email: string;
    session: { access_token: string; refresh_token: string };
  }>("/auth/demo-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
  const me = await apiFetch<{ organizations: Array<{ id: string }> }>("/me", {
    headers: { Authorization: `Bearer ${result.session.access_token}` },
  });
  const organizationId = me.organizations[0]?.id;
  window.localStorage.setItem("busanlink.access_token", result.session.access_token);
  window.localStorage.setItem("busanlink.refresh_token", result.session.refresh_token);
  if (organizationId) window.localStorage.setItem("busanlink.organization_id", organizationId);
  activeSession = { accessToken: result.session.access_token, organizationId: organizationId ?? "" };
  return { accessToken: result.session.access_token, refreshToken: result.session.refresh_token, email: result.email, organizationId };
}

export type BuyerSigningField = {
  field_type: "TEXT" | "SIGNATURE" | "CHECKBOX";
  data_label: string;
  position: Record<string, unknown>;
  size?: { width: number; height: number };
  required?: boolean;
};

/** Sends the seller's original source PDF to Modusign; no second PDF is generated. */
export function requestSigningFromSourceDocument(input: {
  documentId: string;
  title: string;
  buyer: { name: string; email: string };
  fields: BuyerSigningField[];
}): Promise<{ document_id: string; title: string; status: string }> {
  const session = getApiSession();
  return apiFetch("/modusign/requests/from-document", {
    method: "POST",
    headers: new Headers([
      ...authenticatedHeaders(session).entries(),
      ["Idempotency-Key", requestIdempotencyKey("modusign-signing")],
    ]),
    body: JSON.stringify({
      document_id: input.documentId,
      title: input.title,
      buyer: { role: "바이어", ...input.buyer },
      fields: input.fields,
    }),
  });
}
