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
    id: "req-hotel-main",
    contractId: "coastline-hotel-room-2026",
    seller: "해운대 오션스테이",
    title: "2026 해운대 단체 객실 공급 계약",
    type: "revision",
    status: "reviewing",
    createdAt: "2026.07.26",
    guests: 30,
    rooms: 15,
    total: 4380000,
    currency: "KRW",
    currentVersion: "v2",
    revisions: [
      {
        id: "hotel-r1",
        clauseNo: "제2조",
        clauseTitle: "예약 요청 및 확정",
        original: "바이어의 예약 요청은 객실 공급에 대한 청약이며, 셀러가 객실 타입·투숙일·인원·요금을 확인하고 확정 통지를 보낸 때 예약이 성립한다.",
        changeType: "문구 수정",
        requested: "셀러의 확정 통지가 바이어에게 도달한 때 예약이 성립하며, 확정 전에는 객실 확보가 보장되지 않는다는 문구를 추가한다.",
        reason: "예약 요청과 확정 시점을 명확히 구분하고 싶습니다.",
      },
      {
        id: "hotel-r2",
        clauseNo: "제4조",
        clauseTitle: "요금 및 부대비용",
        original: "객실 공급 단가는 객실당 146,000원으로 한다. 세금, 봉사료, 리조트피, 객실 파손 보증금, 미니바 등 부대비용은 별도 고지된 기준에 따라 정산한다.",
        changeType: "문구 수정",
        requested: "포함 비용과 불포함 비용을 별첨으로 분리하고, 현장 추가 비용은 셀러가 증빙과 함께 청구한다.",
        reason: "예약 금액 외 추가 청구가 생길 때 정산 기준을 명확히 하고 싶습니다.",
      },
      {
        id: "hotel-r3",
        clauseNo: "제6조",
        clauseTitle: "오버부킹 및 조건 변경",
        original: "셀러 사정으로 확정 객실 제공이 어려운 경우 셀러는 동급 이상 대체 객실을 제공하거나 바이어와 협의하여 예약을 취소하고 이미 지급된 금액을 환급한다.",
        changeType: "문구 수정",
        requested: "대체 객실은 동일 지역·동급 이상으로 제공하고, 낮은 등급 대체 시 차액과 이동 비용은 셀러가 부담한다.",
        reason: "오버부킹 시 단체 일정 변경 비용의 부담 주체를 명확히 하고 싶습니다.",
      },
    ],
  },
  {
    id: "req-surf-seed",
    contractId: "bluewave-surf-lesson-2026",
    seller: "송정 블루웨이브 서프",
    title: "2026 송정 단체 서핑 강습 공급 계약",
    type: "revision",
    status: "responded",
    createdAt: "2026.07.10",
    revisions: [
      {
        id: "surf-r1",
        clauseNo: "제7조",
        clauseTitle: "보험 및 사고 처리",
        original: "셀러는 영업배상책임보험 또는 이에 준하는 보험에 가입하고, 사고 발생 시 응급 조치와 보험 접수에 협조한다.",
        changeType: "문구 수정",
        requested: "보험명, 보상 한도, 자기부담금, 보상 제외 사유를 별첨으로 제공한다.",
        reason: "안전사고 발생 시 보상 범위를 사전에 확인하고 싶습니다.",
      },
    ],
  },
  {
    id: "req-rental-seed",
    contractId: "route-rental-van-2026",
    seller: "김해공항 루트렌탈",
    title: "2026 김해공항 단체 밴 렌탈 계약",
    type: "asis",
    status: "completed",
    createdAt: "2026.07.18",
    guests: 16,
    rooms: 2,
    total: 528000,
    currency: "KRW",
    message: "공항 픽업과 부산 시내 이동 일정용 밴 2대를 조건 그대로 요청드립니다.",
    currentVersion: "v1",
    latestResponse: "바이어가 공개 조건에 전자서명하여 계약이 체결되었습니다.",
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
