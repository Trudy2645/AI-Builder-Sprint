import { useMemo } from "react";
import { ArrowRight, MessagesSquare } from "lucide-react";
import { useNavigate } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { useRequests } from "../../store/RequestsContext";

export function SellerNegotiatingPage() {
  const navigate = useNavigate();
  const { requests, loading } = useRequests();
  const negotiating = useMemo(() => requests.filter((request) => request.status === "negotiating"), [requests]);
  return <div className="mx-auto max-w-[1000px]"><PageHeader title="협상 중인 계약" description="바이어의 최초 수정 요청과 셀러가 보낸 대안 조건을 확인합니다." />{loading ? <Card className="border-dashed p-16 text-center text-muted-foreground">계약 요청을 불러오는 중입니다…</Card> : negotiating.length === 0 ? <Card className="flex flex-col items-center justify-center gap-3 border-dashed p-10 text-center sm:p-16"><MessagesSquare className="size-7" style={{ color: "var(--ocean)" }} /><p className="text-muted-foreground">현재 협상 중인 계약이 없습니다.</p></Card> : <div className="flex flex-col gap-4">{negotiating.map((request) => <Card key={request.id} className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><Badge className="border-transparent bg-[var(--warning-soft)] text-[var(--warning)]">협상 중</Badge><h2 className="mt-3 text-lg font-semibold" style={{ color: "var(--navy)" }}>{request.title}</h2><p className="mt-1 text-sm text-muted-foreground">{request.buyer ?? "바이어"} · {request.createdAt}</p></div><Button className="gap-1.5" style={{ background: "var(--navy)" }} onClick={() => navigate(request.revisionRequestId ? `/seller/received/${request.revisionRequestId}` : `/seller/received/contract/${request.contractId}`)}>수정 요청 보기<ArrowRight className="size-4" /></Button></div></Card>)}</div>}</div>;
}
