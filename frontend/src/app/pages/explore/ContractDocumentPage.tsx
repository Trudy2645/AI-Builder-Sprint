import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Sparkles,
  AlertTriangle,
  Lightbulb,
  LogOut,
  FilePenLine,
  FileCheck2,
  ChevronRight,
  Download,
  ZoomIn,
  ZoomOut,
  Languages,
} from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useApp } from "../../context/AppContext";
import { useExploreCtx } from "../../hooks/useExploreCtx";
import { getContract, type Contract } from "../../data/contracts";
import { friendlyApiError, getPublicListingAsContract, getPublicSourceDocumentUrl } from "../../lib/api";

type DocLang = "ko" | "en" | "ja" | "zh";
type ClauseTranslation = [title: string, text: string, reason?: string, recommendation?: string];

const DOCUMENT_LANGUAGES: { value: DocLang; label: string }[] = [
  { value: "ko", label: "한국어 원문" },
  { value: "en", label: "English" },
  { value: "ja", label: "日本語" },
  { value: "zh", label: "中文" },
];

const DOCUMENT_COPY: Record<DocLang, Record<string, string>> = {
  ko: {
    original: "계약서 원문", assistant: "AI 계약 비서", intro: "계약서를 바이어 관점에서 분석했습니다.",
    found: "확인 필요 조항", unit: "개", reason: "주의 이유", recommendation: "추천 문구",
    notice: "한국어 원문입니다.", download: "원문", risk: "주의 필요", noRisk: "특이 위험 조항이 발견되지 않았습니다.",
    disclaimer: "AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이나 계약의 법적 효력을 보장하지 않습니다.",
  },
  en: {
    original: "Contract · English", assistant: "AI Contract Assistant", intro: "This contract was reviewed from the buyer's perspective.",
    found: "Clauses requiring attention", unit: "", reason: "Why this needs attention", recommendation: "Suggested wording",
    notice: "AI-translated English version. Please verify it together with the Korean original.", download: "English", risk: "Attention", noRisk: "No notable risk clauses were found.",
    disclaimer: "AI analysis is provided only to assist contract review and does not replace legal advice or guarantee legal validity.",
  },
  ja: {
    original: "契約書・日本語", assistant: "AI契約アシスタント", intro: "バイヤーの観点から契約書を分析しました。",
    found: "確認が必要な条項", unit: "件", reason: "注意が必要な理由", recommendation: "推奨文言",
    notice: "AIによる日本語翻訳です。韓国語の原文と併せて確認してください。", download: "日本語", risk: "要確認", noRisk: "特筆すべきリスク条項は見つかりませんでした。",
    disclaimer: "AI分析は契約確認を補助する参考情報であり、法律相談や契約の法的効力を保証するものではありません。",
  },
  zh: {
    original: "合同·中文", assistant: "AI合同助手", intro: "已从买方角度分析本合同。",
    found: "需要确认的条款", unit: "项", reason: "注意原因", recommendation: "建议措辞",
    notice: "本文件为AI中文翻译，请与韩文原件一并确认。", download: "中文", risk: "需注意", noRisk: "未发现明显的风险条款。",
    disclaimer: "AI分析仅用于辅助合同审查，不构成法律意见，也不保证合同的法律效力。",
  },
};

const TRANSLATED_TITLES: Record<Exclude<DocLang, "ko">, Record<string, string>> = {
  en: {
    "coastline-hotel-room-2026": "2026 Haeundae Group Room Supply Agreement",
    "bluewave-surf-lesson-2026": "2026 Songjeong Group Surf Lesson Supply Agreement",
    "route-rental-van-2026": "2026 Gimhae Airport Group Van Rental Agreement",
  },
  ja: {
    "coastline-hotel-room-2026": "2026年 海雲台団体客室供給契約",
    "bluewave-surf-lesson-2026": "2026年 松亭団体サーフィンレッスン供給契約",
    "route-rental-van-2026": "2026年 金海空港団体バンレンタル契約",
  },
  zh: {
    "coastline-hotel-room-2026": "2026海云台团体客房供应合同",
    "bluewave-surf-lesson-2026": "2026松亭团体冲浪课程供应合同",
    "route-rental-van-2026": "2026金海机场团体面包车租赁合同",
  },
};

const CLAUSE_TRANSLATIONS: Record<Exclude<DocLang, "ko">, Record<string, Record<string, ClauseTranslation>>> = {
  en: {
    "coastline-hotel-room-2026": {
      "제1조": ["Purpose", "This agreement sets the terms under which the Seller supplies group rooms in Haeundae and the Buyer allocates them to a travel itinerary."],
      "제2조": ["Reservation Request and Confirmation", "A reservation is formed when the Seller confirms the room type, stay dates, guests, and rate and sends confirmation to the Buyer.", "If request and confirmation timing are unclear, the Buyer may misunderstand that rooms are already secured.", "State that the reservation is formed only when the Seller's confirmation reaches the Buyer."],
      "제4조": ["Rates and Additional Costs", "The room supply rate is KRW 146,000 per room. Taxes, service charges, resort fees, damage deposits, and minibar charges are settled under separately notified standards.", "The final billed amount may differ if included and excluded costs are not separated.", "Separate included and excluded costs and define who bills and settles on-site additional charges."],
      "제6조": ["Overbooking and Changes", "If the Seller cannot provide confirmed rooms, the Seller will provide equivalent or better rooms or cancel and refund after consultation.", "Unclear replacement standards may cause disputes over schedule changes and extra costs.", "Limit replacement rooms to the same area and equivalent or better grade, with refund and transfer-cost rules for lower-grade replacements."],
    },
    "bluewave-surf-lesson-2026": {
      "제1조": ["Purpose", "This agreement sets the terms for surf lessons and equipment rental supplied to the Buyer's group travelers."],
      "제4조": ["Cancellation and Refunds", "Cancellation is free until three days before use. Cancellation two days before use is charged at 50%, and one-day-before, same-day cancellation, or no-show is charged at 100%.", "Group activities often have changing participant counts, so partial-cancellation rules need to be clear.", "Separate full cancellation and partial participant cancellation, and allow changes within 10% of confirmed participants until one day before use."],
      "제5조": ["Electronic Voucher and Meeting Time", "Refunds may be restricted if participants cannot present the electronic voucher or arrive after the meeting time.", "A strict voucher or lateness rule can overburden the Buyer.", "Provide a backup verification process when the Seller can confirm participants from the booking list."],
      "제7조": ["Insurance and Accident Handling", "The Seller maintains liability insurance or equivalent coverage and cooperates with emergency response and insurance claims.", "Without policy name and coverage limits, the Buyer may face additional accident liability.", "Attach insurance name, coverage limit, deductible, and exclusions."],
    },
    "route-rental-van-2026": {
      "제1조": ["Purpose", "This agreement sets the terms for renting vehicles needed for the Buyer's tourism itinerary and returning them after use."],
      "제4조": ["Cancellation and Replacement Vehicle", "If the Buyer cancels at least 24 hours before rental start, the reservation deposit is refunded. If the Seller cannot provide the reserved vehicle, it offers an equivalent or better replacement or refunds the deposit.", "Replacement grade, seat count, and price-difference standards are unclear.", "Require replacement vehicles to have the same or higher seat count and grade, and refund price differences for lower-priced vehicles."],
      "제5조": ["Insurance and Vehicle Damage Waiver", "The Seller maintains basic auto insurance. Vehicle damage waiver coverage is optional and its scope and deductible are disclosed before contract signing.", "Unclear insurance coverage and deductibles may create unexpected costs after an accident.", "Disclose insurance type, coverage limits, vehicle damage coverage, deductible, and exclusions in writing."],
      "제8조": ["Accident Handling and Loss of Use", "The Buyer must notify the Seller immediately after an accident and cooperate with insurance handling. If damage is attributable to the Buyer, the Seller may claim loss of use with objective calculation evidence.", "Loss-of-use charges may be excessive without objective evidence.", "Allow loss-of-use claims only with repair estimates, repair-period confirmation, and normal rental-rate evidence."],
    },
  },
  ja: {
    "coastline-hotel-room-2026": {
      "제1조": ["契約の目的", "本契約は、セルラーが海雲台地域の団体旅行客向け客室を供給し、バイヤーが旅程に合わせて配分・利用する条件を定めます。"],
      "제2조": ["予約依頼および確定", "セルラーが客室タイプ、宿泊日、人数、料金を確認し、バイヤーに確定通知を送った時点で予約が成立します。", "依頼と確定の時点が曖昧だと、客室が確保済みだと誤解される可能性があります。", "予約成立時点をセルラーの確定通知到達時と明記してください。"],
    },
    "bluewave-surf-lesson-2026": {
      "제1조": ["契約の目的", "団体旅行客向けサーフィンレッスンおよび装備レンタルの提供条件を定めます。"],
      "제7조": ["保険および事故対応", "セルラーは賠償責任保険または同等の保険に加入し、事故時の応急措置と保険受付に協力します。", "保険名と補償限度がない場合、バイヤーが追加責任を負う可能性があります。", "保険名、補償限度、免責金額、補償除外事由を添付してください。"],
    },
    "route-rental-van-2026": {
      "제1조": ["契約の目的", "観光日程に必要な車両を貸し出し、利用後に返却する条件を定めます。"],
      "제5조": ["保険および車両損害免責", "セルラーは基本自動車保険に加入し、車両損害免責の範囲と免責金額を契約前に通知します。", "保険範囲と免責金額が不明確だと事故時に予想外の費用が発生します。", "保険種類、補償限度、車両損害補償、免責金額、除外事由を文書で通知してください。"],
    },
  },
  zh: {
    "coastline-hotel-room-2026": {
      "제1조": ["合同目的", "本合同规定卖方向买方供应海云台团体游客客房，并由买方按行程分配使用的条件。"],
      "제2조": ["预约请求及确认", "卖方确认客房类型、入住日期、人数和价格并向买方发送确认通知时，预约成立。", "如果请求和确认时间不明确，买方可能误认为客房已经 확보。", "请明确预约成立时间为卖方确认通知到达买方时。"],
    },
    "bluewave-surf-lesson-2026": {
      "제1조": ["合同目的", "规定向买方团体游客提供冲浪课程和装备租赁服务的条件。"],
      "제7조": ["保险及事故处理", "卖方应投保营业责任保险或同等保险，并在事故发生时配合急救和保险处理。", "若未说明保险名称和赔偿限额，买方可能承担额外责任。", "请附上保险名称、赔偿限额、自付额及免责事项。"],
    },
    "route-rental-van-2026": {
      "제1조": ["合同目的", "规定卖方向买方出租旅游行程所需车辆并在使用后返还车辆的条件。"],
      "제5조": ["保险及车辆损害免责", "卖方为车辆投保基本汽车保险，并在签约前告知车辆损害免责范围和自付额。", "保险范围和自付额不明确时，事故后可能产生意外费用。", "请书面告知保险种类、赔偿限额、车辆损害保障、自付额和免责事项。"],
    },
  },
};

function translatedArticle(no: string, language: DocLang) {
  if (language === "ko") return no;
  const number = no.replace(/\D/g, "");
  return language === "en" ? `Article ${number}` : `第${number}条`;
}

export function ContractDocumentPage() {
  const { t } = useApp();
  const { base, isGuest } = useExploreCtx();
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const demoContract = getContract(id);
  const [serverContract, setServerContract] = useState<Contract | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  useEffect(() => {
    if (demoContract || !id) return;
    void getPublicListingAsContract(id).then(setServerContract).catch((error: unknown) => setLoadError(friendlyApiError(error)));
  }, [demoContract, id]);
  const [sourcePdfUrl, setSourcePdfUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!id || demoContract) return;
    void getPublicSourceDocumentUrl(id)
      .then((result) => setSourcePdfUrl(result.download_url))
      .catch(() => setSourcePdfUrl(null));
  }, [demoContract, id]);
  const contract = demoContract ?? serverContract;
  const [activeClause, setActiveClause] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [documentLanguage, setDocumentLanguage] = useState<DocLang>("ko");

  if (!contract) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">
        {loadError ?? "계약서 원문을 불러오는 중입니다…"}
      </div>
    );
  }

  const translatedTitle =
    documentLanguage === "ko"
      ? contract.title
      : TRANSLATED_TITLES[documentLanguage][contract.id] ?? contract.title;

  const translatedClauses = contract.clauses.map((clause) => {
    if (documentLanguage === "ko") {
      return { ...clause, sourceNo: clause.no };
    }

    const translated = CLAUSE_TRANSLATIONS[documentLanguage][contract.id]?.[clause.no];
    return {
      ...clause,
      sourceNo: clause.no,
      no: translatedArticle(clause.no, documentLanguage),
      title: translated?.[0] ?? clause.title,
      text: translated?.[1] ?? clause.text,
      risk: clause.risk
        ? {
            reason: translated?.[2] ?? clause.risk.reason,
            recommendation: translated?.[3] ?? clause.risk.recommendation,
          }
        : undefined,
    };
  });
  const risks = translatedClauses.filter((clause) => clause.risk);
  const copy = DOCUMENT_COPY[documentLanguage];

  const jumpTo = (no: string) => {
    setActiveClause(no);
    document.getElementById(`clause-${no}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleRequest = (asIs: boolean) => {
    if (isGuest) {
      toast.info(t("doc.loginToRequest"));
      navigate("/login");
      return;
    }
    if (asIs) {
      navigate(`/buyer/explore/${contract.id}/request${location.search}`);
    } else {
      navigate(`/buyer/explore/${contract.id}/revise${location.search}`);
    }
  };

  const downloadDocument = () => {
    const text = [
      translatedTitle,
      contract.seller,
      documentLanguage === "ko" ? "" : copy.notice,
      "",
      ...translatedClauses.map((clause) => `${clause.no} ${clause.title}\n${clause.text}`),
    ].join("\n\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${translatedTitle}-${documentLanguage}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success(`${copy.download} 계약서 다운로드를 시작했습니다.`);
  };

  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate(`${base}/${contract.id}`)}>
        <ArrowLeft className="size-4" />
        {t("summary.backToList")}
      </Button>

      <div className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 style={{ color: "var(--navy)" }}>{t("doc.title")}</h1>
          <VersionBadge version="v1" />
        </div>
        <div className="mt-1 break-words text-muted-foreground" style={{ fontSize: "14px" }}>
          {contract.seller} · {translatedTitle}
        </div>
      </div>

      {/* Process stepper — step 1 조건 확인 */}
      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <ContractStepper current={1} />
      </div>

      {sourcePdfUrl && (
        <section className="mb-5 overflow-hidden rounded-xl border border-border bg-card sm:mb-6">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-4">
            <div>
              <h3 style={{ color: "var(--navy)" }}>계약서 원문 PDF</h3>
              <p className="mt-1 text-xs text-muted-foreground">셀러가 등록한 원본 PDF입니다. 화면에서 직접 확인할 수 있습니다.</p>
            </div>
            <a className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium hover:bg-muted" href={sourcePdfUrl} target="_blank" rel="noreferrer" download>
              <Download className="size-4" /> PDF 다운로드
            </a>
          </div>
          <iframe title="계약서 원문 PDF" src={sourcePdfUrl} className="h-[75vh] min-h-[560px] w-full" />
        </section>
      )}

      <div className="mb-5 flex flex-col items-stretch justify-between gap-3 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <Languages className="size-5" style={{ color: "var(--ocean)" }} />
          <div>
            <div className="font-semibold" style={{ color: "var(--navy)" }}>계약서 언어</div>
            <div className="text-xs text-muted-foreground">언어를 선택하면 계약서 본문과 AI 분석이 함께 변경됩니다.</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center" role="group" aria-label="계약서 번역 언어 선택">
          {DOCUMENT_LANGUAGES.map((option) => {
            const selected = documentLanguage === option.value;
            return (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={selected ? "default" : "outline"}
                aria-pressed={selected}
                className="w-full min-w-0 whitespace-nowrap sm:w-auto sm:min-w-[82px]"
                style={selected ? { background: "var(--navy)", color: "#fff" } : undefined}
                onClick={() => {
                  setDocumentLanguage(option.value);
                  setActiveClause(null);
                }}
              >
                {option.label}
              </Button>
            );
          })}
        </div>
      </div>

      {documentLanguage !== "ko" && (
        <div
          className="mb-6 flex items-start gap-2 rounded-lg border p-3"
          style={{ borderColor: "var(--ocean)", background: "var(--info-soft)" }}
        >
          <Languages className="mt-0.5 size-4 shrink-0" style={{ color: "var(--ocean)" }} />
          <p className="text-sm leading-6" style={{ color: "var(--navy)" }}>{copy.notice}</p>
        </div>
      )}

      {/* 70:30 layout */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-10 xl:gap-6">
        {/* Left 70% — original text */}
        <div className="xl:col-span-7">
          <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-4">
              <h3 className="whitespace-nowrap" style={{ color: "var(--navy)" }}>{copy.original}</h3>
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge variant="outline" className="gap-1 whitespace-nowrap"><Languages className="size-3.5" />{DOCUMENT_LANGUAGES.find((option) => option.value === documentLanguage)?.label}</Badge>
                <Button variant="outline" size="sm" aria-label="축소" onClick={() => setZoom((value) => Math.max(85, value - 5))}><ZoomOut className="size-4" /></Button>
                <span className="min-w-12 text-center text-xs text-muted-foreground">{zoom}%</span>
                <Button variant="outline" size="sm" aria-label="확대" onClick={() => setZoom((value) => Math.min(120, value + 5))}><ZoomIn className="size-4" /></Button>
                <Button variant="outline" size="sm" className="gap-1 whitespace-nowrap" onClick={downloadDocument}><Download className="size-4" />{copy.download}</Button>
              </div>
            </div>
            <div className="flex flex-col gap-5">
              {translatedClauses.map((cl) => {
                const isRisk = !!cl.risk;
                const isActive = activeClause === cl.sourceNo;
                return (
                  <div
                    key={cl.sourceNo}
                    id={`clause-${cl.sourceNo}`}
                    className="scroll-mt-6 rounded-lg p-3 transition-colors"
                    style={
                      isRisk
                        ? {
                            background: "var(--coral-soft)",
                            border: `1px solid ${isActive ? "var(--coral)" : "transparent"}`,
                          }
                        : undefined
                    }
                  >
                    <div className="flex items-center gap-2">
                      <span className="whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 600 }}>{cl.no}</span>
                      <span style={{ fontWeight: 600 }}>{cl.title}</span>
                      {isRisk && (
                        <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--coral)", color: "#fff" }}>
                          <AlertTriangle className="size-3" />
                          {copy.risk}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-2 text-foreground" style={{ fontSize: `${14 * zoom / 100}px`, lineHeight: 1.8 }}>{cl.text}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right 30% — AI assistant */}
        <div className="xl:col-span-3">
          <div className="rounded-xl border p-4 sm:p-5 xl:sticky xl:top-6" style={{ borderColor: "var(--ocean)", background: "var(--card)" }}>
            <div className="flex items-center gap-2 whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 700 }}>
              <Sparkles className="size-4" />
              {copy.assistant}
            </div>
            <p className="mt-2 text-muted-foreground" style={{ fontSize: "13px", lineHeight: 1.6 }}>
              {copy.intro}
            </p>

            <div className="mt-3 flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--coral)", fontWeight: 600, fontSize: "14px" }}>
              <AlertTriangle className="size-4" />
              {copy.found} {risks.length}{copy.unit}
            </div>

            <div className="mt-3 flex max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1">
              {risks.length === 0 && (
                <p className="text-muted-foreground" style={{ fontSize: "13px" }}>{copy.noRisk}</p>
              )}
              {risks.map((cl) => (
                <button
                  key={cl.sourceNo}
                  type="button"
                  onClick={() => jumpTo(cl.sourceNo)}
                  className="flex flex-col gap-2 rounded-lg border p-3 text-left transition-colors hover:border-[var(--coral)]"
                  style={{ borderColor: "var(--border)", background: "var(--coral-soft)" }}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--coral)", fontWeight: 700, fontSize: "13px" }}>
                      <AlertTriangle className="size-3.5" />
                      {cl.no} {cl.title}
                    </span>
                    <ChevronRight className="size-4 shrink-0" style={{ color: "var(--coral)" }} />
                  </span>
                  <p className="text-foreground" style={{ fontSize: "12px", lineHeight: 1.5 }}>“{cl.text}”</p>
                  <div>
                    <div className="whitespace-nowrap" style={{ color: "var(--coral)", fontSize: "11px", fontWeight: 600 }}>{copy.reason}</div>
                    <p className="text-foreground" style={{ fontSize: "12px", lineHeight: 1.5 }}>{cl.risk!.reason}</p>
                  </div>
                  <div className="rounded-md p-2" style={{ background: "#fff" }}>
                    <div className="flex items-center gap-1 whitespace-nowrap" style={{ color: "var(--teal)", fontSize: "11px", fontWeight: 600 }}>
                      <Lightbulb className="size-3.5" />
                      {copy.recommendation}
                    </div>
                    <p className="mt-0.5 text-foreground" style={{ fontSize: "12px", lineHeight: 1.5 }}>{cl.risk!.recommendation}</p>
                  </div>
                </button>
              ))}
            </div>
            <p className="mt-4 border-t border-border pt-3 text-xs leading-5 text-muted-foreground">{copy.disclaimer}</p>
          </div>
        </div>
      </div>

      {/* Bottom action bar — NO signature button at this stage */}
      <div className="mt-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end">
        <Button variant="ghost" className="w-full gap-1.5 whitespace-nowrap sm:w-auto" onClick={() => navigate(`${base}/${contract.id}`)}>
          <LogOut className="size-4" />
          {t("doc.exit")}
        </Button>
        <Button variant="outline" className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }} onClick={() => handleRequest(false)}>
          <FilePenLine className="size-4" />
          {t("doc.requestRevision")}
        </Button>
        <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: "var(--navy)" }} onClick={() => handleRequest(true)}>
          <FileCheck2 className="size-4" />
          {t("doc.requestAsIs")}
        </Button>
      </div>
    </div>
  );
}
