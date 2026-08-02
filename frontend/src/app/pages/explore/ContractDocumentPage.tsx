import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, ChevronRight, Download, FileCheck2, FilePenLine, Languages, Lightbulb, LogOut, Sparkles, ZoomIn, ZoomOut } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { useApp } from "../../context/AppContext";
import { useExploreCtx } from "../../hooks/useExploreCtx";
import { friendlyApiError, getPublicContractPreview, getPublicListingDetail, type PublicContractPreview, type PublicListingDetail } from "../../lib/api";

type DocLang = "ko" | "en" | "ja" | "zh";
const localeByLanguage = { ko: "ko-KR", en: "en-US", ja: "ja-JP", zh: "zh-CN" } as const;
const languages: Array<{ value: DocLang; label: string }> = [
  { value: "ko", label: "한국어 원문" }, { value: "en", label: "English" }, { value: "ja", label: "日本語" }, { value: "zh", label: "中文" },
];

export function ContractDocumentPage() {
  const { t } = useApp();
  const { id } = useParams();
  const { base, isGuest } = useExploreCtx();
  const navigate = useNavigate();
  const [language, setLanguage] = useState<DocLang>("ko");
  const [detail, setDetail] = useState<PublicListingDetail | null>(null);
  const [preview, setPreview] = useState<PublicContractPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeClause, setActiveClause] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);

  useEffect(() => {
    if (!id) return;
    let active = true;
    Promise.all([getPublicListingDetail(id, localeByLanguage[language]), getPublicContractPreview(id, localeByLanguage[language])])
      .then(([nextDetail, nextPreview]) => { if (active) { setDetail(nextDetail); setPreview(nextPreview); setError(null); } })
      .catch((reason: unknown) => active && setError(friendlyApiError(reason)));
    return () => { active = false; };
  }, [id, language]);

  const clauses = useMemo(() => {
    if (!preview) return [];
    const localized = new Map(preview.localized_content?.clauses.map((item) => [item.clause_id, item]) ?? []);
    return preview.clauses.map((item, index) => ({ ...item, index: index + 1, title: localized.get(item.id)?.title ?? item.title, body: localized.get(item.id)?.body ?? item.body }));
  }, [preview]);
  const findings = preview?.findings ?? [];
  const findingByClause = new Map(findings.filter((item) => item.clause_id).map((item) => [item.clause_id, item]));

  if (error) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{error}</div>;
  if (!detail || !preview) return <div className="rounded-xl border bg-card p-16 text-center text-muted-foreground">AI 계약 분석을 불러오는 중입니다.</div>;

  const jumpTo = (clauseId: string) => {
    setActiveClause(clauseId);
    document.getElementById(`clause-${clauseId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const handleRequest = (asIs: boolean) => {
    if (isGuest) { toast.info(t("doc.loginToRequest")); navigate("/login"); return; }
    navigate(`/buyer/explore/${detail.id}/${asIs ? "request" : "revise"}`);
  };
  const downloadDocument = () => {
    const text = [detail.title, detail.seller.name, ...clauses.map((item) => `제${item.index}조 ${item.title}\n${item.body}`)].join("\n\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${detail.title}-${language}.txt`; anchor.click(); URL.revokeObjectURL(url);
  };

  return <div>
    <Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate(`${base}/${detail.id}`)}><ArrowLeft className="size-4" />{t("summary.backToList")}</Button>
    <div className="mb-4"><div className="flex items-center gap-2"><h1 style={{ color: "var(--navy)" }}>{t("doc.title")}</h1><VersionBadge version="v1" /></div><div className="mt-1 text-sm text-muted-foreground">{detail.seller.name} · {preview.localized_content?.title ?? detail.title}</div></div>
    <div className="mb-6 rounded-xl border bg-card p-5"><ContractStepper current={1} /></div>
    <div className="mb-6 flex flex-col justify-between gap-3 rounded-xl border bg-card p-4 sm:flex-row sm:items-center"><div className="flex items-center gap-2"><Languages className="size-5" style={{ color: "var(--ocean)" }} /><div><div className="font-semibold">계약서 언어</div><div className="text-xs text-muted-foreground">저장된 AI 번역이 있으면 원문과 분석에 함께 적용됩니다.</div></div></div><div className="flex flex-wrap gap-2">{languages.map((option) => <Button key={option.value} size="sm" variant={language === option.value ? "default" : "outline"} style={language === option.value ? { background: "var(--navy)" } : undefined} onClick={() => setLanguage(option.value)}>{option.label}</Button>)}</div></div>
    {language !== "ko" && preview.fallback_locale && <div className="mb-6 rounded-lg border p-3 text-sm" style={{ borderColor: "var(--ocean)", background: "var(--info-soft)" }}>해당 언어의 검증된 AI 번역이 없어 {preview.content_locale} 원문을 표시합니다.</div>}
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-10">
      <div className="xl:col-span-7"><div className="rounded-xl border bg-card p-4 sm:p-6"><div className="mb-4 flex items-center justify-between border-b pb-4"><h3>계약서 원문</h3><div className="flex items-center gap-1.5"><Button variant="outline" size="sm" onClick={() => setZoom((value) => Math.max(85, value - 5))}><ZoomOut className="size-4" /></Button><span className="min-w-12 text-center text-xs">{zoom}%</span><Button variant="outline" size="sm" onClick={() => setZoom((value) => Math.min(120, value + 5))}><ZoomIn className="size-4" /></Button><Button variant="outline" size="sm" onClick={downloadDocument}><Download className="size-4" /></Button></div></div><div className="flex flex-col gap-5">{clauses.map((clause) => { const finding = findingByClause.get(clause.id); return <div key={clause.id} id={`clause-${clause.id}`} className="scroll-mt-6 rounded-lg p-3" style={finding ? { background: "var(--coral-soft)", border: `1px solid ${activeClause === clause.id ? "var(--coral)" : "transparent"}` } : undefined}><div className="flex items-center gap-2"><span style={{ color: "var(--ocean)", fontWeight: 600 }}>제{clause.index}조</span><strong>{clause.title}</strong>{finding && <Badge style={{ background: "var(--coral)" }}>주의 필요</Badge>}</div><p className="mt-2 leading-8" style={{ fontSize: `${14 * zoom / 100}px` }}>{clause.body}</p></div>; })}</div></div></div>
      <div className="xl:col-span-3"><div className="rounded-xl border bg-card p-5 xl:sticky xl:top-6" style={{ borderColor: "var(--ocean)" }}><div className="flex items-center gap-2 font-bold" style={{ color: "var(--ocean)" }}><Sparkles className="size-4" />AI 계약 비서</div><p className="mt-2 text-sm text-muted-foreground">저장된 바이어 관점 분석 결과입니다.</p><div className="mt-3 flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--coral)" }}><AlertTriangle className="size-4" />확인 필요 조항 {findings.length}개</div><div className="mt-3 flex max-h-[60vh] flex-col gap-3 overflow-y-auto">{findings.length === 0 && <p className="text-sm text-muted-foreground">AI finding이 없습니다.</p>}{findings.map((finding) => { const clause = clauses.find((item) => item.id === finding.clause_id); return <button key={finding.id ?? `${finding.clause_id}-${finding.explanation}`} type="button" onClick={() => finding.clause_id && jumpTo(finding.clause_id)} className="rounded-lg border p-3 text-left" style={{ background: "var(--coral-soft)" }}><span className="flex items-center justify-between text-sm font-bold" style={{ color: "var(--coral)" }}>{clause ? `제${clause.index}조 ${clause.title}` : "계약 전체"}<ChevronRight className="size-4" /></span><p className="mt-2 text-xs leading-5">{finding.explanation}</p>{finding.suggested_text && <div className="mt-2 rounded-md bg-white p-2"><div className="flex items-center gap-1 text-xs font-semibold" style={{ color: "var(--teal)" }}><Lightbulb className="size-3.5" />추천 문구</div><p className="mt-1 text-xs leading-5">{finding.suggested_text}</p></div>}</button>; })}</div><p className="mt-4 border-t pt-3 text-xs leading-5 text-muted-foreground">AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이 아닙니다.</p></div></div>
    </div>
    <div className="mt-6 flex flex-col justify-end gap-2 rounded-xl border bg-card p-4 sm:flex-row"><Button variant="ghost" onClick={() => navigate(`${base}/${detail.id}`)}><LogOut className="size-4" />{t("doc.exit")}</Button><Button variant="outline" style={{ color: "var(--ocean)" }} onClick={() => handleRequest(false)}><FilePenLine className="size-4" />{t("doc.requestRevision")}</Button><Button style={{ background: "var(--navy)" }} onClick={() => handleRequest(true)}><FileCheck2 className="size-4" />{t("doc.requestAsIs")}</Button></div>
  </div>;
}
