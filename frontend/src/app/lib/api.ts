import type { Category } from "./catalog";

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
  if (token) {
    window.localStorage.setItem(accessTokenKey, token);
    // Keep the legacy key in sync while existing sessions migrate.
    window.localStorage.setItem("busanlink.access_token", token);
    activeSession = null;
  }
  else {
    window.localStorage.removeItem(accessTokenKey);
    window.localStorage.removeItem("busanlink.access_token");
    activeSession = null;
  }
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(accessTokenKey)
    ?? window.localStorage.getItem("busanlink.access_token");
}

type ApiSession = {
  accessToken: string;
  organizationId: string;
};

let activeSession: ApiSession | null = null;

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function clearApiSession(): void {
  activeSession = null;
  window.localStorage.removeItem("busanlink.access_token");
  window.localStorage.removeItem("busanlink.refresh_token");
  window.localStorage.removeItem("busanlink.organization_id");
  setAccessToken(null);
}

type UploadedDocumentProcessingResult = {
  listingId: string;
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
  if (activeSession) return validateApiSession(activeSession);
  const accessToken = getAccessToken()
    ?? import.meta.env.VITE_API_ACCESS_TOKEN;
  const organizationId = window.localStorage.getItem("busanlink.organization_id")
    ?? import.meta.env.VITE_SELLER_ORGANIZATION_ID;
  return validateApiSession({ accessToken: accessToken ?? "", organizationId: organizationId ?? "" });
}

function validateApiSession(session: ApiSession): ApiSession {
  const { accessToken, organizationId } = session;
  if (!accessToken || !organizationId) {
    throw new Error("API 로그인 정보가 없습니다. 로그인 후 다시 시도해 주세요.");
  }
  if (!uuidPattern.test(organizationId)) {
    clearApiSession();
    throw new Error("셀러 조직 정보가 UUID 형식이 아닙니다. 셀러 계정으로 다시 로그인해 주세요.");
  }
  return session;
}

export function hasApiSession(): boolean {
  const accessToken = getAccessToken()
    ?? window.localStorage.getItem("busanlink.access_token")
    ?? import.meta.env.VITE_API_ACCESS_TOKEN;
  const organizationId = window.localStorage.getItem("busanlink.organization_id")
    ?? import.meta.env.VITE_SELLER_ORGANIZATION_ID;
  return Boolean(accessToken && organizationId);
}

function authenticatedHeaders(session: ApiSession, headers: HeadersInit = {}): Headers {
  const result = new Headers(headers);
  result.set("Authorization", `Bearer ${session.accessToken}`);
  result.set("X-Organization-Id", session.organizationId);
  return result;
}

export function friendlyApiError(error: unknown): string {
  if (error instanceof ApiError) {
    const messages: Record<string, string> = {
      AUTH_REQUIRED: "로그인이 필요합니다. 로그인한 뒤 다시 시도해 주세요.",
      LISTING_NOT_FOUND: "요청한 공고를 찾을 수 없거나 더 이상 공개되지 않았습니다.",
      LISTING_NOT_AVAILABLE: "이 공고는 현재 계약을 받을 수 없습니다. 다른 공고를 선택해 주세요.",
      SERVICE_PERIOD_UNAVAILABLE: "선택한 이용 기간에는 이 상품을 이용할 수 없습니다.",
      PEOPLE_OUT_OF_RANGE: "입력한 인원이 상품의 허용 인원 범위를 벗어났습니다.",
      QUANTITY_REQUIRED: "객실·차량 등 필요한 수량을 입력해 주세요.",
      UNSUPPORTED_DISPLAY_CURRENCY: "현재는 상품 기준 통화로만 예상 금액을 계산할 수 있습니다.",
      DATABASE_UNAVAILABLE: "서비스 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      INVALID_STATE_TRANSITION: "이미 처리되었거나 현재 상태에서는 변경할 수 없는 요청입니다.",
    };
    if (error.message.includes("X-Organization-Id")) {
      return "셀러 조직 정보가 올바르지 않습니다. 셀러 계정으로 다시 로그인한 뒤 시도해 주세요.";
    }
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
  const accessToken = getAccessToken();
  if (accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const organizationId = window.localStorage.getItem("busanlink.organization_id");
  if (organizationId && !headers.has("X-Organization-Id")) {
    headers.set("X-Organization-Id", organizationId);
  }
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

  const listing = await apiFetch<{ listing_id: string; version_no: number }>("/seller/listings", {
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

export type SellerListingDraftInput = {
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
  available: boolean;
};

const PRICE_UNIT_MAP: Record<string, { apiUnit: string; quantityUnit: string }> = {
  "객실당": { apiUnit: "room_night", quantityUnit: "room" },
  "1인당": { apiUnit: "person", quantityUnit: "person" },
  "1동당": { apiUnit: "room", quantityUnit: "room" },
  "1좌석당": { apiUnit: "seat", quantityUnit: "seat" },
  // The backend currently has no team-level unit. Keep the existing UI option
  // usable by storing it as a person-priced listing until a team unit exists.
  "1팀당": { apiUnit: "person", quantityUnit: "person" },
};

function positiveInteger(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function sellerListingTerms(draft: SellerListingDraftInput): Record<string, unknown> {
  const priceUnit = PRICE_UNIT_MAP[draft.priceUnit] ?? PRICE_UNIT_MAP["1인당"];
  return {
    service_start_date: draft.availabilityStart || null,
    service_end_date: draft.availabilityEnd || null,
    supply_quantity_description: draft.quantity || null,
    quantity_unit: priceUnit.quantityUnit,
    minimum_quantity: positiveInteger(draft.minQty),
    maximum_quantity: positiveInteger(draft.maxQty),
    base_price_amount_minor: draft.unitPrice ? Number.parseInt(draft.unitPrice, 10) : null,
    currency: "KRW",
    price_unit: priceUnit.apiUnit,
    cancellation_policy: draft.cancellation || null,
    no_show_policy: draft.noShow || null,
    // The form has one cancellation/refund field, so preserve that same text
    // in the canonical refund field instead of dropping it.
    refund_policy: draft.cancellation || null,
    settlement_policy: draft.settlement || null,
    liability_policy: draft.liability || null,
    termination_policy: draft.termination || null,
    special_terms: draft.special || null,
    price_display_basis: draft.priceUnit || null,
    contract_availability_note: draft.available ? null : "현재 계약 요청을 받지 않습니다.",
  };
}

async function updateSellerListingPresentation(
  listingId: string,
  draft: SellerListingDraftInput,
): Promise<void> {
  const session = getApiSession();
  await apiFetch(`/seller/listings/${listingId}/presentation`, {
    method: "PATCH",
    headers: authenticatedHeaders(session, { "Content-Type": "application/json" }),
    body: JSON.stringify({
      display_title: draft.productName,
      public_headline: draft.headline || null,
    }),
  });
}

export async function updateSellerListingTerms(
  listingId: string,
  terms: Record<string, unknown> = {},
  baseVersionNo = 1,
): Promise<void> {
  const session = getApiSession();
  const body = {
    ...terms,
    base_price_amount_minor: terms.base_price_amount_minor == null
      ? null
      : Number(terms.base_price_amount_minor),
    currency: String(terms.currency || "KRW"),
    price_unit: String(terms.price_unit || "room_night"),
    quantity_unit: String(terms.quantity_unit || "room"),
    supply_quantity_description: terms.supply_quantity_description == null
      ? null
      : String(terms.supply_quantity_description),
    cancellation_policy: terms.cancellation_policy == null ? null : String(terms.cancellation_policy),
    no_show_policy: terms.no_show_policy == null ? null : String(terms.no_show_policy),
    refund_policy: terms.refund_policy == null ? null : String(terms.refund_policy),
    settlement_policy: terms.settlement_policy == null ? null : String(terms.settlement_policy),
    liability_policy: terms.liability_policy == null ? null : String(terms.liability_policy),
    termination_policy: terms.termination_policy == null ? null : String(terms.termination_policy),
  };
  await apiFetch(`/seller/listings/${listingId}/terms`, {
    method: "PATCH",
    headers: authenticatedHeaders(session, { "Content-Type": "application/json" }),
    body: JSON.stringify({ base_version_no: baseVersionNo, terms: body }),
  });
}

export async function createSellerListing(
  draft: SellerListingDraftInput,
): Promise<{ listing_id: string; version_no: number }> {
  const session = getApiSession();
  return apiFetch<{ listing_id: string; version_no: number }>("/seller/listings", {
    method: "POST",
    headers: new Headers([
      ...authenticatedHeaders(session, { "Content-Type": "application/json" }).entries(),
      ["Idempotency-Key", requestIdempotencyKey("listing-create")],
    ]),
    body: JSON.stringify({
      creation_method: "manual",
      title: draft.productName,
      category: draft.category,
      district: draft.district,
      language: "ko-KR",
    }),
  });
}

export async function saveSellerListing(
  draft: SellerListingDraftInput,
  publish: boolean,
): Promise<{ listingId: string; versionNo: number }> {
  const created = await createSellerListing(draft);
  await updateSellerListingTerms(created.listing_id, sellerListingTerms(draft), created.version_no);
  await updateSellerListingPresentation(created.listing_id, draft);
  if (publish) await publishSellerListing(created.listing_id);
  return { listingId: created.listing_id, versionNo: created.version_no };
}

export async function finalizeSellerListing(
  listingId: string,
  draft: SellerListingDraftInput,
  publish: boolean,
  baseVersionNo = 1,
): Promise<void> {
  await updateSellerListingTerms(listingId, sellerListingTerms(draft), baseVersionNo);
  await updateSellerListingPresentation(listingId, draft);
  if (publish) await publishSellerListing(listingId);
}

export async function registerPublishedSellerListing(input: SellerListingDraftInput & {
  listingId?: string;
  baseVersionNo?: number;
  sourceDocumentId?: string;
  method: "write" | "upload";
}): Promise<SellerListingSummary> {
  const draft: SellerListingDraftInput = { ...input, available: true };
  let listingId = input.listingId;
  if (listingId) await finalizeSellerListing(listingId, draft, true, input.baseVersionNo ?? 1);
  else listingId = (await saveSellerListing(draft, true)).listingId;
  if (input.sourceDocumentId) {
    const session = getApiSession();
    await apiFetch(`/seller/listings/${listingId}/presentation`, {
      method: "PATCH",
      headers: authenticatedHeaders(session, { "Content-Type": "application/json" }),
      body: JSON.stringify({ hero_document_id: input.sourceDocumentId }),
    });
  }
  const listing = (await getSellerListings()).find((item) => item.id === listingId);
  if (!listing || listing.status !== "published") throw new Error("공고 공개 상태를 확인하지 못했습니다.");
  return listing;
}

export async function publishSellerListing(listingId: string): Promise<void> {
  const session = getApiSession();
  await apiFetch(`/seller/listings/${listingId}/complete`, { method: "POST", headers: authenticatedHeaders(session) });
  await apiFetch(`/seller/listings/${listingId}/publish`, { method: "POST", headers: authenticatedHeaders(session) });
}

export async function pauseSellerListing(listingId: string): Promise<void> {
  const session = getApiSession();
  await apiFetch(`/seller/listings/${listingId}/pause`, {
    method: "POST",
    headers: authenticatedHeaders(session),
  });
}

export async function archiveSellerListing(listingId: string): Promise<void> {
  const session = getApiSession();
  await apiFetch(`/seller/listings/${listingId}/archive`, {
    method: "POST",
    headers: authenticatedHeaders(session),
  });
}

export async function changeSellerListingStatus(listingId: string, action: "publish" | "pause" | "archive"): Promise<void> {
  if (action === "publish") return publishSellerListing(listingId);
  if (action === "pause") return pauseSellerListing(listingId);
  return archiveSellerListing(listingId);
}
export type Role = "buyer" | "seller";

type AuthSession = { access_token: string; refresh_token: string; token_type: string; expires_in: number };
export type AuthResponse = { user_id: string; email: string; role?: Role; organization_id?: string | null; session: AuthSession | null };

function persistAuthResponse(result: AuthResponse): void {
  const accessToken = result.session?.access_token;
  const refreshToken = result.session?.refresh_token;
  const organizationId = result.organization_id;
  if (!accessToken) return;
  window.localStorage.setItem("busanlink.access_token", accessToken);
  if (refreshToken) window.localStorage.setItem("busanlink.refresh_token", refreshToken);
  setAccessToken(accessToken);
  if (organizationId && uuidPattern.test(organizationId)) {
    window.localStorage.setItem("busanlink.organization_id", organizationId);
    activeSession = { accessToken, organizationId };
  } else {
    window.localStorage.removeItem("busanlink.organization_id");
    activeSession = null;
  }
}

export async function loginWithPassword(email: string, password: string): Promise<AuthResponse> {
  const result = await apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  persistAuthResponse(result);
  return result;
}

export async function signup(payload: Record<string, unknown>): Promise<AuthResponse> {
  const result = await apiFetch<AuthResponse>("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  persistAuthResponse(result);
  return result;
}

export type ContractListItem = {
  id: string;
  listing_id: string | null;
  listing_title: string;
  seller_name: string;
  initial_request_kind: "as_is" | "revision";
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

export type SellerContractListItem = {
  contract_id: string;
  listing_id: string | null;
  listing_title: string;
  buyer_name: string;
  buyer_group_name: string | null;
  requested_people: number;
  service_start_date: string;
  service_end_date: string;
  amount_minor: number | null;
  currency: string | null;
  initial_request_kind: "as_is" | "revision";
  request_kind_label: string;
  status: string;
  status_label: string;
  requested_at: string;
};

export function getReceivedContracts(): Promise<SellerContractListItem[]> {
  const session = getApiSession();
  return apiFetch<SellerContractListItem[]>("/seller/contracts/received", {
    headers: authenticatedHeaders(session),
  });
}

export const getSellerReceivedContracts = getReceivedContracts;

export type SellerDashboard = {
  stats: {
    published_listings: number;
    received_requests: number;
    seller_review: number;
    revision_requested: number;
    signing: number;
    signed: number;
    cancelled: number;
  };
  recent_requests: SellerContractListItem[];
  listing_request_counts: Array<{
    listing_id: string;
    listing_title: string;
    listing_status: string;
    request_count: number;
  }>;
};

export function getSellerDashboard(): Promise<SellerDashboard> {
  const session = getApiSession();
  return apiFetch<SellerDashboard>("/seller/dashboard", {
    headers: authenticatedHeaders(session),
  });
}

export type ContractDetail = {
  id: string;
  listing_id: string | null;
  listing_title: string;
  status: string;
  bucket: string;
  status_label: string;
  has_unread_response: boolean;
  initial_request_kind: "as_is" | "revision";
  request_message: string | null;
  requested_people: number;
  buyer_group_name: string | null;
  signing_capacity: "self" | "group_representative";
  amount_minor: number | null;
  currency: string | null;
  service_start_date: string;
  service_end_date: string;
  created_at: string;
  updated_at: string;
  parties: Array<{ role: "buyer" | "seller"; name: string }>;
  terms: {
    people: number;
    quantity: number;
    quantity_unit: string;
    nights: number;
    start_date: string;
    end_date: string;
    amount_minor: number | null;
    currency: string | null;
    formula: string;
  };
  current_version: {
    id: string;
    version_no: number;
    title: string;
    body: string;
    clauses: Array<{ id: string; clause_order: number; clause_key: string | null; title: string; body: string }>;
  };
};

export type ContractVersionListItem = {
  id: string;
  version_no: number;
  version_label: string;
  title: string;
  created_by_role: "buyer" | "seller" | "system";
  creation_reason: "contract_created" | "revision_agreement" | "manual_version";
  created_from_revision_request_id: string | null;
  created_at: string;
  clause_count: number;
  risk: { score: number | null; finding_count: number };
};

export type ContractVersionCompare = {
  contract_id: string;
  from_version: ContractVersionListItem;
  to_version: ContractVersionListItem;
  clause_summary: { added: number; deleted: number; modified: number };
  clause_changes: Array<{
    change_type: "added" | "deleted" | "modified";
    before: { id: string; clause_order: number; clause_key: string | null; title: string; body: string } | null;
    after: { id: string; clause_order: number; clause_key: string | null; title: string; body: string } | null;
  }>;
  price_change: {
    direction: "increased" | "decreased" | "unchanged" | "unknown";
    before: { amount_minor: number | null; currency: string | null };
    after: { amount_minor: number | null; currency: string | null };
    delta_amount_minor: number | null;
  };
  period_change: {
    changed: boolean | null;
    before: { start_date: string | null; end_date: string | null };
    after: { start_date: string | null; end_date: string | null };
  };
  risk_change: {
    direction: "increased" | "decreased" | "unchanged" | "unknown";
    before_score: number | null;
    after_score: number | null;
    before_finding_count: number;
    after_finding_count: number;
  };
};

export function getContractVersions(contractId: string): Promise<ContractVersionListItem[]> {
  return apiFetch<ContractVersionListItem[]>(`/contracts/${contractId}/versions`);
}

export function compareContractVersions(
  contractId: string,
  fromVersion: number,
  toVersion: number,
): Promise<ContractVersionCompare> {
  const query = new URLSearchParams({ from: String(fromVersion), to: String(toVersion) });
  return apiFetch<ContractVersionCompare>(`/contracts/${contractId}/versions/compare?${query}`);
}

export type ContractRequestPayload = {
  people: number;
  quantity: number;
  quantity_unit: string;
  nights: number;
  start_date: string;
  end_date: string;
  currency: string;
  group_name?: string;
  signing_capacity?: "self" | "group_representative";
  request_message?: string;
  initial_request_kind: "as_is" | "revision";
};

export type ContractRequestCreated = {
  contract_id: string;
  version_no: number;
  status: "seller_review" | "revision_requested";
};

export function createContractRequest(
  listingId: string,
  payload: ContractRequestPayload,
): Promise<ContractRequestCreated> {
  return apiFetch(`/listings/${listingId}/contract-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": requestIdempotencyKey("contract-request") },
    body: JSON.stringify(payload),
  });
}

export const createPublicContractRequest = createContractRequest;

export type RevisionItemPayload = {
  request_type: "modify" | "delete" | "add";
  clause_id?: string;
  reason: string;
  requested_text?: string;
  document_ids?: string[];
};

export function generateRevisionSuggestion(payload: {
  request_type: "modify" | "add";
  clause_id?: string;
  clause_title?: string;
  original_text?: string;
  reason: string;
}): Promise<{ suggestion: string }> {
  return apiFetch<{ suggestion: string }>("/ai-guidance/revision-suggestion", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": requestIdempotencyKey("revision-suggestion"),
    },
    body: JSON.stringify(payload),
  });
}

export type RevisionGuidanceItem = {
  id: string;
  impact: string;
  recommendation: string;
  rejection_reason: string;
};

export function generateRevisionGuidance(items: Array<{
  id: string;
  clause_title: string;
  original_text: string;
  requested_text: string;
  reason: string;
}>): Promise<{ items: RevisionGuidanceItem[] }> {
  return apiFetch<{ items: RevisionGuidanceItem[] }>("/ai-guidance/revision-impact", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": requestIdempotencyKey("revision-impact"),
    },
    body: JSON.stringify({ items }),
  });
}

export type RevisionRequestResponse = {
  id: string;
  contract_id: string;
  base_version_no: number;
  status: "draft" | "sent" | "accepted" | "rejected" | "partially_accepted" | "countered" | "cancelled";
  requested_by_user_id: string;
  message: string | null;
  seller_message: string | null;
  response_message: string | null;
  items: Array<{
    id: string;
    item_order: number;
    request_type: "modify" | "delete" | "add";
    clause_id?: string;
    reason: string;
    requested_text?: string;
    document_ids?: string[];
  }>;
  decision_preview: {
    resulting_clauses: Array<{ id: string; clause_order: number; clause_key: string | null; title: string; body: string }>;
    pending_item_count: number;
    requires_buyer_response: boolean;
    will_create_version: boolean;
  };
  created_at: string;
  updated_at: string;
  sent_at: string | null;
  decided_at: string | null;
  responded_at: string | null;
};

export function createRevisionRequest(
  contractId: string,
  payload: { base_version_no: number; message?: string; items: RevisionItemPayload[] },
): Promise<{ revision_request_id: string; status: string; contract_id: string; contract_status: string; version_no: number | null; replayed: boolean }> {
  return apiFetch(`/contracts/${contractId}/revision-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": requestIdempotencyKey("revision-request") },
    body: JSON.stringify(payload),
  });
}

export function getRevisionRequest(revisionRequestId: string): Promise<RevisionRequestResponse> {
  return apiFetch<RevisionRequestResponse>(`/revision-requests/${revisionRequestId}`);
}

export function sendRevisionRequest(revisionRequestId: string): Promise<{ revision_request_id: string; status: string; contract_id: string; contract_status: string; version_no: number | null; replayed: boolean }> {
  return apiFetch(`/revision-requests/${revisionRequestId}/send`, {
    method: "POST",
    headers: { "Idempotency-Key": requestIdempotencyKey("revision-send") },
  });
}

export type SellerRevisionRequestListItem = {
  id: string;
  contract_id: string;
  listing_title: string;
  buyer_name: string;
  status: "draft" | "sent" | "accepted" | "rejected" | "partially_accepted" | "countered" | "cancelled";
  message: string | null;
  item_count: number;
  item_summary: string[];
  has_unread: boolean;
  sent_at: string | null;
  updated_at: string;
};

export function getSellerRevisionRequests(): Promise<SellerRevisionRequestListItem[]> {
  return apiFetch<SellerRevisionRequestListItem[]>("/seller/revision-requests?status=sent&status=countered");
}

export function decideRevisionRequest(
  revisionRequestId: string,
  payload: { seller_message?: string },
): Promise<{ revision_request_id: string; status: string; contract_id: string; contract_status: string; version_no: number | null; replayed: boolean }> {
  return apiFetch(`/revision-requests/${revisionRequestId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": requestIdempotencyKey("revision-decide") },
    body: JSON.stringify(payload),
  });
}

export function patchRevisionItem(
  revisionRequestId: string,
  itemId: string,
  payload: { decision: "accepted" | "rejected" | "countered"; seller_reason?: string; counter_text?: string },
): Promise<RevisionRequestResponse> {
  return apiFetch<RevisionRequestResponse>(`/revision-requests/${revisionRequestId}/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export const decideRevisionItem = patchRevisionItem;

export type MeProfile = {
  id: string;
  email: string | null;
  username: string;
  display_name: string;
  phone: string | null;
  country_code: string | null;
  locale: "ko-KR" | "en-US" | "ja-JP" | "zh-CN";
  preferred_currency: string;
  default_group_name: string | null;
  affiliation_name: string | null;
  business_type: string | null;
  role: "buyer" | "seller";
  created_at: string;
  updated_at: string;
  organizations: Array<{ id: string; name: string; verification_status: string; member_role: string }>;
};

export function getMe(): Promise<MeProfile> {
  return apiFetch<MeProfile>("/me");
}

export function updateMe(payload: Record<string, unknown>): Promise<MeProfile> {
  return apiFetch<MeProfile>("/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export type OrganizationProfile = {
  id: string;
  organization_type: "seller";
  legal_name: string | null;
  business_registration_no: string | null;
  representative_name: string | null;
  business_address: string | null;
  supply_categories: Category[];
  verification_status: "pending" | "verified" | "rejected";
  rating_average: number | string;
  rating_count: number;
  member_role: string;
  created_at: string;
  updated_at: string;
  verified_at: string | null;
};

export function getOrganization(organizationId: string): Promise<OrganizationProfile> {
  return apiFetch<OrganizationProfile>(`/organizations/${organizationId}`);
}

export function updateOrganization(
  organizationId: string,
  payload: Record<string, unknown>,
): Promise<OrganizationProfile> {
  return apiFetch<OrganizationProfile>(`/organizations/${organizationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getPublicContractPreview(
  listingId: string,
  locale: "ko-KR" | "en-US" | "ja-JP" | "zh-CN" = "ko-KR",
): Promise<{
  listing_version_id: string;
  body: string;
  clauses: PublicListingClause[];
  findings: Array<{
    id: string | null;
    clause_id: string | null;
    severity: "high" | "medium" | "low" | "none";
    explanation: string;
    suggested_text: string;
    disclaimer: string;
    evidence_refs: Array<{ id: string; label: string; document_title: string; source_kind: string; page: number; section: string | null; excerpt: string }>;
  }>;
  requested_locale: string;
  content_locale: string;
  fallback_locale: string | null;
}> {
  return apiFetch(`/public/listings/${listingId}/contract-preview?locale=${encodeURIComponent(locale)}`);
}

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

export function dispatchSignatureRequest(contractId: string, versionId: string): Promise<SignatureRequest> {
  return apiFetch<SignatureRequest>(`/contracts/${contractId}/versions/${versionId}/signature-requests/dispatch`, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
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
  seller: { name: string; rating: number | string; rating_count: number; verified: boolean };
  title: string;
  district: string;
  category: "vehicle_rental" | "activity" | "tour" | "accommodation";
  hero_image_url: string | null;
  public_headline: string | null;
  ai_summary: string | null;
  base_price: { amount_minor: number; currency: string; unit: string | null } | null;
  availability: { start_date: string | null; end_date: string | null };
  status: "published" | "paused";
  contract_available: boolean;
  attention_required_count: number;
};

export type SellerListingSummary = {
  id: string;
  title: string;
  display_title: string | null;
  category: "vehicle_rental" | "activity" | "tour" | "accommodation";
  district: string;
  status: "draft" | "processing" | "ready" | "published" | "paused" | "expired" | "archived";
  creation_method: "manual" | "upload";
  public_headline: string | null;
  service_start_date: string | null;
  service_end_date: string | null;
  supply_quantity_description: string | null;
  base_price: { amount_minor: number; currency: string; unit: string | null } | null;
  contract_available: boolean;
  attention_required_count: number;
  contract_request_count: number;
  created_at: string;
  updated_at: string;
};

export type SellerListingDetail = SellerListingSummary & {
  language: "ko-KR" | "en-US" | "ja-JP" | "zh-CN";
  display_company_name: string | null;
  seller_description: string | null;
  ai_summary: string | null;
  hero_document_id: string | null;
  terms: {
    service_start_date: string | null;
    service_end_date: string | null;
    supply_quantity: number | null;
    quantity_unit: string | null;
    minimum_quantity: number | null;
    maximum_quantity: number | null;
    people_per_unit: number | null;
    base_price_amount_minor: number | null;
    currency: string | null;
    price_unit: string | null;
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
    price_display_basis: string | null;
    contract_availability_note: string | null;
  };
  current_version: {
    id: string;
    version_no: number;
    title: string;
    body: string;
    created_at: string;
    clauses: Array<{ id: string; clause_order: number; clause_key: string | null; title: string; body: string }>;
  };
  published_at: string | null;
  paused_at: string | null;
};

export function getSellerListings(): Promise<SellerListingSummary[]> {
  const session = getApiSession();
  return apiFetch<SellerListingSummary[]>("/seller/listings", {
    headers: authenticatedHeaders(session),
  });
}

export function getSellerListing(listingId: string): Promise<SellerListingDetail> {
  const session = getApiSession();
  return apiFetch<SellerListingDetail>(`/seller/listings/${listingId}`, {
    headers: authenticatedHeaders(session),
  });
}

export function getPublicListings(): Promise<PublicListing[]> {
  return apiFetch<PublicListing[]>("/public/listings");
}

export type PublicListingClause = {
  id: string;
  clause_key: string | null;
  title: string;
  body: string;
  highlight: "critical" | "warning" | "info" | null;
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
  price_display_basis: string | null;
  contract_availability_note: string | null;
  vat_included: null;
  clauses: PublicListingClause[];
};

export function getPublicListing(
  listingId: string,
  locale: "ko-KR" | "en-US" | "ja-JP" | "zh-CN" = "ko-KR",
): Promise<PublicListingDetail> {
  return apiFetch<PublicListingDetail>(
    `/public/listings/${encodeURIComponent(listingId)}?locale=${encodeURIComponent(locale)}`,
  );
}

export type ContractTranslationLocale = "en-US" | "ja-JP" | "zh-CN";

export type ContractTranslation = {
  locale: ContractTranslationLocale;
  title: string;
  clauses: Array<{ id: string; title: string; body: string }>;
};

export function translatePublicContract(
  listing: PublicListingDetail,
  targetLocale: ContractTranslationLocale,
): Promise<ContractTranslation> {
  return apiFetch<ContractTranslation>("/ai-guidance/contract-translation", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": requestIdempotencyKey(`contract-translation-${targetLocale}`),
    },
    body: JSON.stringify({
      target_locale: targetLocale,
      title: listing.title,
      clauses: listing.clauses.map(({ id, title, body }) => ({ id, title, body })),
    }),
  });
}

export type ContractAssistantFinding = {
  clause_id: string;
  severity: "high" | "medium" | "low";
  explanation: string;
  suggested_text: string | null;
};

export function analyzePublicContract(
  listing: PublicListingDetail,
): Promise<{ findings: ContractAssistantFinding[] }> {
  return apiFetch<{ findings: ContractAssistantFinding[] }>("/ai-guidance/contract-assistant", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": requestIdempotencyKey("buyer-contract-assistant"),
    },
    body: JSON.stringify({
      title: listing.title,
      clauses: listing.clauses.map(({ id, title, body }) => ({ id, title, body })),
    }),
  });
}

export function generateChangeSummary(
  changes: Array<{ title: string; before?: string; after?: string }>,
): Promise<{ lines: string[] }> {
  return apiFetch<{ lines: string[] }>("/ai-guidance/change-summary", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": requestIdempotencyKey("public-summary"),
    },
    body: JSON.stringify({ changes }),
  });
}

export function generatePublicListingSummary(
  listing: PublicListingDetail,
): Promise<{ lines: string[] }> {
  const period = [listing.availability.start_date, listing.availability.end_date]
    .filter(Boolean)
    .join(" ~ ");
  const price = listing.base_price
    ? `${listing.base_price.amount_minor.toLocaleString("ko-KR")} ${listing.base_price.currency}${listing.base_price.unit ? ` · ${listing.base_price.unit}` : ""}`
    : "정보 없음";
  const clauses = listing.clauses
    .slice(0, 12)
    .map((clause, index) => `제${index + 1}조 ${clause.title}: ${clause.body}`)
    .join("\n");

  return generateChangeSummary([
    {
      title: "상품 및 공급 조건",
      after: [
        `상품: ${listing.title}`,
        `판매자: ${listing.seller.name}`,
        `지역: ${listing.district}`,
        `공급 기간: ${period || "정보 없음"}`,
        `공급 수량: ${listing.supply_quantity_description ?? "정보 없음"}`,
      ].join("\n"),
    },
    {
      title: "가격 및 정산 조건",
      after: [
        `기준 가격: ${price}`,
        `정산: ${listing.settlement_policy ?? "정보 없음"}`,
        `최소 기준: ${listing.minimum_quantity ?? listing.minimum_people ?? "정보 없음"}`,
      ].join("\n"),
    },
    {
      title: "취소·노쇼·주요 조항",
      after: [
        `취소: ${listing.cancellation_policy ?? "정보 없음"}`,
        `노쇼: ${listing.no_show_policy ?? "정보 없음"}`,
        clauses || "주요 조항 정보 없음",
      ].join("\n"),
    },
  ]);
}

export function getPublicSourceDocumentUrl(listingId: string): Promise<{ document_id: string; download_url: string; expires_at: string }> {
  const token = getAccessToken();
  if (!token) throw new ApiError({ code: "AUTH_REQUIRED", message: "Login required." });
  return apiFetch(`/public/listings/${encodeURIComponent(listingId)}/source-document-url`, { headers: { Authorization: `Bearer ${token}` } });
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
    details: { period: `${listing.availability.start_date ?? "미정"} ~ ${listing.availability.end_date ?? "미정"}`, supplyQuantity: listing.supply_quantity_description ?? "미정", unitPrice: `${(listing.base_price?.amount_minor ?? 0).toLocaleString("ko-KR")} ${listing.base_price?.currency ?? "KRW"}`, cancellation: listing.cancellation_policy ?? "미정", noShow: listing.no_show_policy ?? "미정", settlement: listing.settlement_policy ?? "미정" },
    clauses: listing.clauses.map((clause, index) => ({ id: clause.id, no: `제${index + 1}조`, title: clause.title, text: clause.body })),
  };
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
  setAccessToken(result.session.access_token);
  window.localStorage.setItem("busanlink.refresh_token", result.session.refresh_token);
  if (organizationId && uuidPattern.test(organizationId)) {
    window.localStorage.setItem("busanlink.organization_id", organizationId);
    activeSession = { accessToken: result.session.access_token, organizationId };
  } else {
    window.localStorage.removeItem("busanlink.organization_id");
    activeSession = null;
  }
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
      title: input.title,
      buyer: { role: "바이어", ...input.buyer },
      fields: input.fields,
    }),
  });
}
