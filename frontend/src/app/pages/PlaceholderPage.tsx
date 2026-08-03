import {
  ArrowRight,
  Building2,
  FileCheck2,
  IdCard,
  Mail,
  MapPin,
  PenLine,
  Phone,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ContractStepper } from "../components/contract/ContractStepper";
import { useApp } from "../context/AppContext";
import { useRequests } from "../store/RequestsContext";
import { useListings } from "../store/ListingsContext";
import { useNegotiation } from "../store/NegotiationContext";
import { formatKRW } from "../data/contracts";

function NegotiatingView({ base }: { base: string }) {
  const navigate = useNavigate();
  const { requests } = useRequests();
  const request = requests.find((item) => item.id === "req-hotel-main");

  return (
    <div>
      <PageHeader
        title="협상 중인 계약"
        description="상대방의 조항별 응답과 계약서 변경 내용을 확인하고 최종안을 검토하세요."
      />
      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5"><ContractStepper current={3} /></div>
      <Card className="p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Badge className="border-transparent" style={{ background: "var(--warning-soft)", color: "var(--warning)" }}>
                {request?.status === "responded" ? "셀러 응답 도착" : "협상 중"}
              </Badge>
            </div>
            <h2 style={{ color: "var(--navy)" }}>{request?.title || "2026 해운대 단체 객실 공급 계약"}</h2>
            <p className="mt-1 text-sm text-muted-foreground">GlobalTrip Japan ↔ 해운대 오션스테이</p>
          </div>
          <div className="text-right">
            <div className="text-xs text-muted-foreground">예상 계약 금액</div>
            <div className="mt-1 text-lg font-bold" style={{ color: "var(--navy)" }}>{formatKRW(request?.total || 4350000)}</div>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {[
            ["제4조 취소", "셀러 대안 제시", "7일 전 무료 · 이후 50%"],
            ["제5조 노쇼", "요청 수락", "1박 공급 요금 100%"],
            ["제6조 정산", "요청 수락", "익월 15일까지 지급"],
          ].map(([title, state, detail]) => (
            <div key={title} className="rounded-lg border border-border p-4">
              <div className="text-sm font-semibold">{title}</div>
              <div className="mt-2 text-xs font-semibold" style={{ color: state === "요청 수락" ? "var(--success)" : "var(--ocean)" }}>{state}</div>
              <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-lg p-4" style={{ background: "var(--info-soft)" }}>
          <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--ocean)" }}><ShieldCheck className="size-4" />AI 변경 요약</div>
          <p className="mt-2 text-sm leading-6">취소 기한과 위약금, 노쇼 비용, 지급일이 구체화되어 양측의 해석 차이와 정산 지연 위험이 감소했습니다.</p>
        </div>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
          <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/signing`)}>
            최종안 검토 <ArrowRight className="size-4" />
          </Button>
        </div>
      </Card>
    </div>
  );
}

function ContractsView({ base }: { base: string }) {
  const navigate = useNavigate();
  const { requests } = useRequests();
  const { bothSigned, contractNo } = useNegotiation();
  const completed = requests.filter((request) => request.status === "completed");
  const rows = bothSigned && !completed.some((request) => request.id === "req-hotel-main")
    ? [requests.find((request) => request.id === "req-hotel-main"), ...completed].filter(Boolean)
    : completed;

  return (
    <div>
      <PageHeader title="체결 계약" description="양측 전자서명이 완료된 최종 계약과 계약서를 관리하세요." />
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-5"><div className="text-sm text-muted-foreground">체결 완료</div><div className="mt-2 text-3xl font-bold" style={{ color: "var(--navy)" }}>{Math.max(rows.length, 1)}</div></Card>
        <Card className="p-5"><div className="text-sm text-muted-foreground">이번 달 체결</div><div className="mt-2 text-3xl font-bold" style={{ color: "var(--success)" }}>{bothSigned ? 1 : 0}</div></Card>
        <Card className="p-5"><div className="text-sm text-muted-foreground">전자서명 완료율</div><div className="mt-2 text-3xl font-bold" style={{ color: "var(--ocean)" }}>100%</div></Card>
      </div>
      <div className="mt-6 space-y-3 md:hidden">
        {rows.map((request) => (
          <Card key={request!.id} className="p-4">
            <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="line-clamp-2 text-base" style={{ color: "var(--navy)" }}>{request!.title}</h3><p className="mt-1 truncate text-sm text-muted-foreground">{request!.seller}</p></div></div>
            <div className="mt-3 border-y border-border py-3 text-sm"><span className="text-muted-foreground">체결일</span><span className="float-right">{bothSigned ? "2026.07.29" : request!.createdAt}</span></div>
            <Button className="mt-3 w-full whitespace-nowrap" variant="outline" onClick={() => navigate(bothSigned ? `${base}/signing/complete` : `${base}/signing`)}>{bothSigned ? "계약 상세" : "계약 확인"}</Button>
          </Card>
        ))}
      </div>
      <Card className="mt-6 hidden overflow-x-auto md:block">
        <div className="grid min-w-[760px] grid-cols-[1.3fr_1.8fr_1fr_1fr] gap-4 border-b bg-muted/40 px-5 py-3 text-xs font-semibold text-muted-foreground">
          <div>상대 업체</div><div>계약명</div><div>체결일</div><div>작업</div>
        </div>
        {rows.map((request) => (
          <div key={request!.id} className="grid min-w-[760px] grid-cols-[1.3fr_1.8fr_1fr_1fr] items-center gap-4 border-b px-5 py-4 last:border-b-0">
            <div className="font-semibold">{request!.seller}</div>
            <div className="truncate">{request!.title}</div>
            <div className="text-sm text-muted-foreground">{bothSigned ? "2026.07.29" : request!.createdAt}</div>
            <Button size="sm" variant="outline" className="whitespace-nowrap" onClick={() => navigate(bothSigned ? `${base}/signing/complete` : `${base}/signing`)}>
              {bothSigned ? "계약 상세" : "계약 확인"}
            </Button>
          </div>
        ))}
      </Card>
      {contractNo && <p className="mt-3 text-right text-xs text-muted-foreground">최근 계약번호 {contractNo}</p>}
    </div>
  );
}

function SellerProfileView() {
  const { listings, publicCount } = useListings();
  return (
    <div>
      <PageHeader title="셀러 마이페이지" description="사업자 정보와 계약 공고·협상·체결 현황을 확인하고 수정하세요." />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(280px,.75fr)]">
        <Card className="min-w-0 p-4 sm:p-6">
          <div className="mb-5 flex min-w-0 items-center gap-4">
            <div className="flex size-14 items-center justify-center rounded-xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}><Building2 className="size-7" /></div>
            <div className="min-w-0"><h2 className="break-words" style={{ color: "var(--navy)" }}>해운대 오션스테이</h2><div className="mt-1 flex items-center gap-1.5 text-sm" style={{ color: "var(--success)" }}><ShieldCheck className="size-4 shrink-0" />사업자 인증 완료</div></div>
          </div>
          <div className="grid gap-3 xl:grid-cols-2">
            {[
              [UserRound, "대표자", "김민수"], [IdCard, "사업자등록번호", "617-81-20260"],
              [Mail, "담당자 이메일", "contract@oceanstay.co.kr"], [Phone, "전화번호", "051-740-2026"],
              [MapPin, "사업장 주소", "부산광역시 해운대구 해운대해변로 264"], [FileCheck2, "공급 분야", "숙박"],
            ].map(([Icon, label, value]) => {
              const RowIcon = Icon as typeof Building2;
              return <div key={String(label)} className="min-w-0 rounded-lg border border-border p-4"><div className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground"><RowIcon className="size-3.5 shrink-0" />{String(label)}</div><div className={String(value).includes("@") ? "mt-1 break-all font-semibold" : "mt-1 break-words font-semibold"}>{String(value)}</div></div>;
            })}
          </div>
          <div className="mt-5 grid grid-cols-1 gap-2 sm:flex sm:flex-wrap"><Button variant="outline">정보 수정</Button><Button variant="outline">비밀번호 변경</Button></div>
        </Card>
        <div className="grid grid-cols-2 gap-3">
          {[
            ["임시저장 공고", listings.filter((item) => item.status === "draft").length],
            ["공개 중인 공고", publicCount], ["받은 요청", 3], ["협상 중", 2], ["서명 대기", 1], ["체결 완료", 4],
          ].map(([label, value]) => <Card key={String(label)} className="p-4"><div className="text-xs text-muted-foreground">{String(label)}</div><div className="mt-2 text-2xl font-bold" style={{ color: "var(--navy)" }}>{String(value)}건</div></Card>)}
        </div>
      </div>
    </div>
  );
}

export function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useApp();
  const { pathname } = useLocation();
  const base = pathname.startsWith("/seller") ? "/seller" : "/buyer";

  if (pathname.endsWith("/negotiating")) return <NegotiatingView base={base} />;
  if (pathname.endsWith("/contracts")) return <ContractsView base={base} />;
  if (pathname === "/seller/mypage") return <SellerProfileView />;

  return (
    <div>
      <PageHeader title={t(titleKey)} />
      <Card className="flex flex-col items-center justify-center gap-3 border-dashed p-10 text-center sm:p-16">
        <PenLine className="size-7" style={{ color: "var(--ocean)" }} />
        <p className="text-muted-foreground">이 기능은 데모 흐름에서 연결되는 화면입니다.</p>
      </Card>
    </div>
  );
}
