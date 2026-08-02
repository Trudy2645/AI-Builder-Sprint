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

type ApiSession = {
  accessToken: string;
  organizationId: string;
};

let activeSession: ApiSession | null = null;

type UploadedDocumentProcessingResult = {
  listingId: string;
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
    const messages: Record<string, string> = {
      AUTH_REQUIRED: "로그인이 필요합니다. 로그인한 뒤 다시 시도해 주세요.",
      LISTING_NOT_FOUND: "요청한 공고를 찾을 수 없거나 더 이상 공개되지 않았습니다.",
      LISTING_NOT_AVAILABLE: "이 공고는 현재 계약을 받을 수 없습니다. 다른 공고를 선택해 주세요.",
      SERVICE_PERIOD_UNAVAILABLE: "선택한 이용 기간에는 이 상품을 이용할 수 없습니다.",
      PEOPLE_OUT_OF_RANGE: "입력한 인원이 상품의 허용 인원 범위를 벗어났습니다.",
      QUANTITY_REQUIRED: "객실·차량 등 필요한 수량을 입력해 주세요.",
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
