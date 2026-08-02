import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Download, FileCheck2, FilePenLine, Languages, Lightbulb, LogOut, ZoomIn, ZoomOut } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useApp } from "../../context/AppContext";
import { useExploreCtx } from "../../hooks/useExploreCtx";
import {
  friendlyApiError,
  getPublicContractPreview,
  getPublicListing,
  type PublicListingDetail,
} from "../../lib/api";

type DocumentLanguage = "ko-KR" | "en-US" | "ja-JP" | "zh-CN";
const DOCUMENT_LANGUAGES: Array<{ value: DocumentLanguage; label: string }> = [
  { value: "ko-KR", label: "한국어 원문" },
  { value: "en-US", label: "English" },
  { value: "ja-JP", label: "日本語" },
  { value: "zh-CN", label: "中文" },
];

function dateLabel(value: string | null): string {
  return value ? value.replace(/-/g, ".") : "정보 없음";
}

export function ContractDocumentPage() {
  const { t } = useApp();
  const { base, isGuest } = useExploreCtx();
  const { id } = useParams();
  const navigate = useNavigate();
  const [language, setLanguage] = useState<DocumentLanguage>("ko-KR");
  const [listing, setListing] = useState<PublicListingDetail | null>(null);
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof getPublicContractPreview>> | null>(null);
  const [zoom, setZoom] = useState(100);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    setLoading(true);
    Promise.all([getPublicListing(id, language), getPublicContractPreview(id, language)])
      .then(([nextListing, nextPreview]) => {
        if (!active) return;
        setListing(nextListing);
        setPreview(nextPreview);
        setError(null);
      })
      .catch((reason: unknown) => { if (active) setError(friendlyApiError(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, language]);

  const clauses = useMemo(() => {
    if (!listing) return [];
    return listing.clauses.map((clause) => {
      const finding = preview?.findings.find((item) => item.clause_id === clause.id && item.severity !== "none");
      return { ...clause, finding };
    });
  }, [listing, preview]);

  if (loading) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">계약서를 불러오는 중입니다…</div>;
  if (error || !listing) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{error ?? t("explore.empty")}</div>;

  const download = () => {
    const content = [listing.title, listing.seller.name, "", ...clauses.map((clause) => `${clause.title}\n${clause.body}`)].join("\n\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${listing.title}-${language}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("계약서 다운로드를 시작했습니다.");
  };

  const request = (revision: boolean) => {
    if (isGuest) {
      toast.info("계약 요청은 로그인 후 이용할 수 있습니다.");
      navigate("/login");
      return;
    }
    navigate(`${base}/${listing.id}/${revision ? "revise" : "request"}`);
  };

  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate(`${base}/${listing.id}`)}>
        <ArrowLeft className="size-4" />{t("summary.backToList")}
      </Button>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h1 style={{ color: "var(--navy)" }}>{listing.title}</h1>
        <VersionBadge version="v1" />
      </div>
      <p className="mb-5 text-sm text-muted-foreground">{listing.seller.name} · {dateLabel(listing.availability.start_date)} ~ {dateLabel(listing.availability.end_date)}</p>
      <div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={1} /></div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2"><Languages className="size-5" style={{ color: "var(--ocean)" }} /><span className="font-semibold">계약서 언어</span></div>
        <div className="flex flex-wrap gap-2">
          {DOCUMENT_LANGUAGES.map((option) => <Button key={option.value} size="sm" variant={language === option.value ? "default" : "outline"} onClick={() => setLanguage(option.value)}>{option.label}</Button>)}
        </div>
      </div>
      {language !== "ko-KR" && <div className="mb-5 rounded-lg border border-[var(--ocean)] bg-[var(--info-soft)] p-3 text-sm">AI 번역본입니다. 한국어 원문과 함께 확인해 주세요.</div>}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-10 xl:gap-6">
        <div className="xl:col-span-7">
          <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-4">
              <h2 className="font-semibold">계약서 원문</h2>
              <div className="flex items-center gap-1.5"><Button variant="outline" size="sm" onClick={() => setZoom((value) => Math.max(85, value - 5))}><ZoomOut className="size-4" /></Button><span className="w-12 text-center text-xs">{zoom}%</span><Button variant="outline" size="sm" onClick={() => setZoom((value) => Math.min(120, value + 5))}><ZoomIn className="size-4" /></Button><Button variant="outline" size="sm" onClick={download}><Download className="mr-1 size-4" />다운로드</Button></div>
            </div>
            <div className="space-y-5" style={{ fontSize: `${zoom / 100}em` }}>
              {clauses.map((clause, index) => <section key={clause.id} className="rounded-lg border border-border p-4"><h3 className="flex items-center gap-2 text-base"><span style={{ color: "var(--ocean)" }}>제{index + 1}조</span>{clause.title}{clause.finding && <Badge className="border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}>확인 필요</Badge>}</h3><p className="mt-2 leading-7">{clause.body}</p></section>)}
            </div>
          </div>
        </div>
        <aside className="xl:col-span-3">
          <div className="sticky top-20 rounded-xl border border-[var(--ocean)] bg-[var(--info-soft)] p-5"><div className="flex items-center gap-1.5 font-semibold" style={{ color: "var(--ocean)" }}><Lightbulb className="size-4" />AI 계약 비서</div><p className="mt-2 text-sm leading-6">{preview?.findings.length ? `${preview.findings.length}개 조항에 확인이 필요합니다.` : "확인 필요 조항이 없습니다."}</p>{preview?.findings.map((finding) => <div key={finding.id ?? finding.clause_id} className="mt-3 rounded-lg bg-card p-3 text-sm"><div className="font-semibold">{finding.severity.toUpperCase()}</div><p className="mt-1 leading-6">{finding.explanation}</p>{finding.suggested_text && <p className="mt-2 text-muted-foreground">추천: {finding.suggested_text}</p>}</div>)}<p className="mt-4 text-xs leading-5 text-muted-foreground">AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이 아닙니다.</p></div>
        </aside>
      </div>
      <div className="mt-6 flex flex-wrap justify-end gap-2 rounded-xl border border-border bg-card p-4"><Button variant="outline" onClick={() => request(false)}><FileCheck2 className="mr-1 size-4" />조건 그대로 요청</Button><Button style={{ background: "var(--navy)" }} onClick={() => request(true)}><FilePenLine className="mr-1 size-4" />수정 요청</Button><Button variant="ghost" onClick={() => navigate(base)}><LogOut className="mr-1 size-4" />나가기</Button></div>
    </div>
  );
}
