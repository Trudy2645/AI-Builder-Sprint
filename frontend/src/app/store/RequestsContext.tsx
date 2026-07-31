import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";

export type RequestStatus =
  | "draft" // 작성 중
  | "reviewing" // 셀러 검토 중
  | "responded" // 응답 도착
  | "negotiating" // 협상 중
  | "signing" // 서명 대기
  | "completed" // 체결 완료
  | "closed"; // 종료

export type RequestType = "asis" | "revision";

export interface RevisionItem {
  id: string;
  clauseNo: string;
  clauseTitle: string;
  original: string;
  changeType: string; // 문구 수정 / 삭제 요청 / 추가 요청
  requested: string;
  reason: string;
  attachment?: string;
}

export interface SentRequest {
  id: string;
  contractId: string;
  seller: string;
  title: string;
  type: RequestType;
  status: RequestStatus;
  createdAt: string; // YYYY.MM.DD
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

const seed: SentRequest[] = [
  {
    id: "req-summer-main",
    contractId: "ocean-stay-2026-summer",
    seller: "해운대 오션스테이",
    title: "2026 부산 여름 패키지 객실 공급 계약",
    type: "revision",
    status: "reviewing",
    createdAt: "2026.07.26",
    guests: 30,
    rooms: 15,
    total: 4350000,
    currency: "KRW",
    currentVersion: "v2",
    revisions: [
      {
        id: "main-r1",
        clauseNo: "제4조",
        clauseTitle: "취소 및 환불",
        original: "바이어는 필요에 따라 예약을 무료로 취소할 수 있다.",
        changeType: "문구 수정",
        requested: "체크인 5일 전까지 무료 취소하고 이후에는 객실 1박 요금의 30%를 부과한다.",
        reason: "무료 취소 기한과 수수료를 명확히 하고 싶습니다.",
      },
      {
        id: "main-r2",
        clauseNo: "제5조",
        clauseTitle: "노쇼",
        original: "노쇼 발생 시 처리 기준은 별도로 정하지 않는다.",
        changeType: "기준 추가",
        requested: "노쇼 시 해당 객실의 1박 요금 100%를 부과한다.",
        reason: "노쇼 발생 시 정산 범위를 명확히 하고 싶습니다.",
      },
      {
        id: "main-r3",
        clauseNo: "제6조",
        clauseTitle: "정산 및 지급",
        original: "객실 이용 금액은 추후 정산한다.",
        changeType: "문구 수정",
        requested: "매월 말 이용 내역을 마감하고 익월 15일까지 바이어가 셀러에게 지급한다.",
        reason: "대금 지급 시점과 지급 주체를 명확히 하고 싶습니다.",
      },
    ],
  },
  {
    id: "req-seed-1",
    contractId: "gwangan-seabreeze",
    seller: "광안 씨브리즈 호텔",
    title: "2026 광안리 오션뷰 객실 공급 계약",
    type: "revision",
    status: "responded",
    createdAt: "2026.07.10",
    revisions: [
      {
        id: "rv-1",
        clauseNo: "제3조",
        clauseTitle: "정산 및 지급",
        original: "정산은 매월 말 마감 후 익익월(60일) 15일에 지급한다.",
        changeType: "문구 수정",
        requested: "정산은 매월 말 마감 후 익월 15일에 지급한다.",
        reason: "60일 정산 주기는 운전자금 부담이 큽니다. 30일로 단축을 요청합니다.",
      },
    ],
  },
  {
    id: "req-seed-2",
    contractId: "songjeong-surf",
    seller: "송정 서핑클럽",
    title: "2026 송정 서핑 강습 패키지 공급 계약",
    type: "asis",
    status: "completed",
    createdAt: "2026.07.18",
    guests: 30,
    rooms: 0,
    total: 1950000,
    currency: "KRW",
    message: "8월 단체 강습 일정 확정을 위해 조건 그대로 요청드립니다.",
    currentVersion: "v1",
    latestResponse: "바이어가 공개 조건에 전자서명하여 계약이 체결되었습니다.",
  },
  {
    id: "req-seed-3",
    contractId: "gijang-glamping",
    seller: "기장 오션 글램핑",
    title: "2026 기장 오션뷰 글램핑 공급 계약",
    type: "revision",
    status: "signing",
    createdAt: "2026.06.28",
    rooms: 10,
    total: 1750000,
    currency: "KRW",
  },
  {
    id: "req-seed-4",
    contractId: "busan-city-package",
    seller: "부산 시티투어 파트너스",
    title: "2026 부산 시티 하이라이트 패키지 공급 계약",
    type: "revision",
    status: "completed",
    createdAt: "2026.05.30",
    revisions: [],
  },
];

export function RequestsProvider({ children }: { children: ReactNode }) {
  const { isDemoSession } = useApp();
  const [requests, setRequests] = useState<SentRequest[]>([]);

  useEffect(() => {
    setRequests(isDemoSession ? seed : []);
  }, [isDemoSession]);

  const addRequest: RequestsContextValue["addRequest"] = (r) => {
    const now = new Date();
    const createdAt = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}`;
    const id = `req-${Date.now()}`;
    setRequests((prev) => [
      { ...r, id, createdAt },
      ...prev,
    ]);
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
