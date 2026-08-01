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

export function signup(payload: Record<string, unknown>): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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
