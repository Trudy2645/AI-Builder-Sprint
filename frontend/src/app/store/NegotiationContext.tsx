import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Role } from "../context/AppContext";

interface NegotiationState {
  flow: "negotiated" | "direct";
  directRequestId?: string;
  directContractId?: string;
  directContract?: {
    title: string;
    seller: string;
    period: string;
    total: number;
    currency: string;
    guests?: number;
    rooms: number;
    nights: number;
  };
  buyerApproved: boolean;
  sellerApproved: boolean;
  buyerSigned: boolean;
  sellerSigned: boolean;
  contractNo?: string;
  signedAt?: string;
}

interface NegotiationContextValue extends NegotiationState {
  bothApproved: boolean;
  bothSigned: boolean;
  approve: (role: Role) => void;
  sign: (role: Role) => void;
  startDirectSignature: (
    requestId: string,
    contractId: string,
    contract: NonNullable<NegotiationState["directContract"]>,
  ) => void;
  reset: () => void;
}

const NegotiationContext = createContext<NegotiationContextValue | null>(null);

const initialState: NegotiationState = {
  flow: "negotiated",
  buyerApproved: false,
  sellerApproved: false,
  buyerSigned: false,
  sellerSigned: false,
};

function genContractNo(): string {
  const now = new Date();
  const y = now.getFullYear();
  const rand = String(Math.floor(1000 + Math.random() * 9000));
  return `BL-${y}-${rand}`;
}

function nowStamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function NegotiationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<NegotiationState>(initialState);

  const approve = (role: Role) =>
    setState((s) => ({
      ...s,
      buyerApproved: role === "buyer" ? true : s.buyerApproved,
      sellerApproved: role === "seller" ? true : s.sellerApproved,
    }));

  const sign = (role: Role) =>
    setState((s) => {
      const next: NegotiationState = {
        ...s,
        buyerSigned: role === "buyer" ? true : s.buyerSigned,
        sellerSigned: role === "seller" ? true : s.sellerSigned,
      };
      if (next.buyerSigned && next.sellerSigned && !next.contractNo) {
        next.contractNo = genContractNo();
        next.signedAt = nowStamp();
      }
      return next;
    });

  // 셀러가 공개한 조건은 사전 동의된 제안으로 간주한다.
  // 바이어가 조건을 그대로 선택하면 협상·최종 검토 없이 바이어 서명만 진행한다.
  const startDirectSignature = (
    requestId: string,
    contractId: string,
    contract: NonNullable<NegotiationState["directContract"]>,
  ) =>
    setState({
      flow: "direct",
      directRequestId: requestId,
      directContractId: contractId,
      directContract: contract,
      buyerApproved: true,
      sellerApproved: true,
      buyerSigned: false,
      sellerSigned: true,
      contractNo: undefined,
      signedAt: undefined,
    });

  const reset = () => setState(initialState);

  const value = useMemo<NegotiationContextValue>(
    () => ({
      ...state,
      bothApproved: state.buyerApproved && state.sellerApproved,
      bothSigned: state.buyerSigned && state.sellerSigned,
      approve,
      sign,
      startDirectSignature,
      reset,
    }),
    [state],
  );

  return <NegotiationContext.Provider value={value}>{children}</NegotiationContext.Provider>;
}

export function useNegotiation() {
  const ctx = useContext(NegotiationContext);
  if (!ctx) throw new Error("useNegotiation must be used within NegotiationProvider");
  return ctx;
}
