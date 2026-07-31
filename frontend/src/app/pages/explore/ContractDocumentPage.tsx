import { useState } from "react";
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
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useApp } from "../../context/AppContext";
import { useExploreCtx } from "../../hooks/useExploreCtx";
import { getContract } from "../../data/contracts";

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
    "ocean-stay-2026-summer": "2026 Busan Summer Room Supply Agreement",
    "gwangan-seabreeze": "2026 Gwangalli Ocean-view Room Supply Agreement",
    "marina-yacht-tour": "2026 Yacht Sunset Tour Seat Supply Agreement",
    "songjeong-surf": "2026 Songjeong Surf Lesson Supply Agreement",
    "busan-city-tour": "2026 Busan City Highlights Tour Supply Agreement",
    "gijang-glamping": "2026 Gijang Ocean-view Glamping Supply Agreement",
  },
  ja: {
    "ocean-stay-2026-summer": "2026年 釜山サマー客室供給契約",
    "gwangan-seabreeze": "2026年 広安里オーシャンビュー客室供給契約",
    "marina-yacht-tour": "2026年 ヨット・サンセットツアー座席供給契約",
    "songjeong-surf": "2026年 松亭サーフィンレッスン供給契約",
    "busan-city-tour": "2026年 釜山シティハイライトツアー供給契約",
    "gijang-glamping": "2026年 機張オーシャンビューグランピング供給契約",
  },
  zh: {
    "ocean-stay-2026-summer": "2026釜山夏季客房供应合同",
    "gwangan-seabreeze": "2026广安里海景客房供应合同",
    "marina-yacht-tour": "2026游艇日落之旅座位供应合同",
    "songjeong-surf": "2026松亭冲浪课程供应合同",
    "busan-city-tour": "2026釜山城市精选旅游供应合同",
    "gijang-glamping": "2026机张海景豪华露营供应合同",
  },
};

const CLAUSE_TRANSLATIONS: Record<Exclude<DocLang, "ko">, Record<string, Record<string, ClauseTranslation>>> = {
  en: {
    "ocean-stay-2026-summer": {
      "제1조": ["Purpose", "This agreement sets the terms under which the Seller (Haeundae Ocean Stay) supplies peak-season rooms for summer 2026 to the Buyer for sale and distribution."],
      "제2조": ["Supply Period and Quantity", "The supply period is July 1 through August 31, 2026. Up to 30 rooms will be supplied on weekends (Friday and Saturday), with additional weekday rooms subject to mutual agreement."],
      "제3조": ["Supply Price", "The room supply price is KRW 145,000 per room, excluding VAT."],
      "제4조": ["Cancellation and Refunds", "The Buyer may cancel reservations free of charge as needed.", "No free-cancellation deadline or later fee standard is stated, so the Seller may bear cancellation risk until immediately before check-in.", "Specify free cancellation until seven days before check-in and a fee equal to 50% of one night's room charge thereafter."],
      "제5조": ["No-show Policy", "No separate standard is established for no-shows.", "Without a charge standard for guests who do not arrive, the parties may dispute the amount to be settled.", "Specify a no-show charge equal to 100% of the applicable one-night room rate."],
      "제6조": ["Settlement and Payment", "Room usage charges will be settled at a later date.", "The payment date and responsible payer are unclear, which may cause delayed settlement or unpaid-balance disputes.", "Close usage records at each month-end and require the Buyer to pay the Seller by the 15th of the following month."],
      "제8조": ["Dispute Resolution", "Any dispute arising from this agreement will be subject to the Busan District Court as the court of first instance."],
    },
    "gwangan-seabreeze": {
      "제1조": ["Purpose", "This agreement sets the conditions under which the Seller supplies Gwangalli ocean-view rooms to the Buyer."],
      "제2조": ["Supply Period and Quantity", "Up to 40 rooms will be supplied on weekdays and weekends from June 15 through September 15, 2026."],
      "제3조": ["Settlement and Payment", "Payment is made on the 15th of the second month following each month-end close, a cycle of approximately 60 days.", "A 60-day settlement cycle is longer than the usual 30-day standard and may increase the Buyer's working-capital burden.", "Shorten payment to the 15th of the following month or add an early-settlement discount if the 60-day term remains."],
      "제4조": ["Cancellation and No-show", "Cancellation is free until five days before check-in; a no-show is charged at 80% of one night's room rate."],
    },
    "marina-yacht-tour": {
      "제1조": ["Purpose", "This agreement sets the supply conditions for seats on the yacht sunset tour."],
      "제2조": ["Liability for Safety Accidents", "The Seller is liable for safety accidents during the tour when the guest is not at fault, but compensation is limited to KRW 5 million per person.", "The per-person cap may expose the Buyer to additional liability in the event of a serious accident.", "Require the Seller to maintain commercial liability insurance and remove a separate cap for losses covered by that insurance."],
      "제3조": ["Adverse Weather", "If the tour is cancelled due to adverse weather, the full amount will be refunded or the schedule will be changed."],
    },
    "songjeong-surf": {
      "제1조": ["Purpose", "This agreement sets the supply conditions for the surfing lesson product."],
      "제2조": ["Cancellation Policy", "Cancellation is free until one day before use; same-day cancellations are charged the full lesson fee.", "The one-day deadline may create a high cancellation-fee burden when a group reservation changes.", "For group bookings of ten or more, extend the free-cancellation deadline to three days before use."],
    },
    "busan-city-tour": {
      "제1조": ["Purpose", "This agreement sets the supply conditions for the Busan city tour."],
      "제2조": ["Price Structure", "Peak-season and off-season prices are applied separately, with a detailed price schedule attached."],
    },
    "gijang-glamping": {
      "제1조": ["Purpose", "This agreement sets the supply conditions for ocean-view glamping units."],
      "제2조": ["Cancellation and Settlement", "Cancellation is free until seven days before check-in, and payment is due on the 15th of the following month."],
    },
  },
  ja: {
    "ocean-stay-2026-summer": {
      "제1조": ["契約の目的", "本契約は、セルラー（海雲台オーシャンステイ）がバイヤーに2026年夏の繁忙期客室を供給し、バイヤーが販売・流通するための条件を定めることを目的とします。"],
      "제2조": ["供給期間および数量", "供給期間は2026年7月1日から8月31日までとし、週末（金・土）は最大30室を供給します。平日の客室は双方の協議により追加供給できます。"],
      "제3조": ["供給単価", "客室供給単価は1室145,000ウォン（VAT別）とします。"],
      "제4조": ["取消および返金", "バイヤーは必要に応じて予約を無料で取り消すことができます。", "無料取消の期限とその後の手数料基準がなく、セルラーがチェックイン直前まで取消リスクを負う可能性があります。", "チェックイン7日前まで無料とし、それ以降は1泊料金の50％を請求する基準を明記してください。"],
      "제5조": ["ノーショー対応", "ノーショー発生時の処理基準は別途定めません。", "来館しない予約者の料金基準がないため、精算範囲について紛争になる可能性があります。", "ノーショー時は該当客室の1泊料金100％を請求すると明記してください。"],
      "제6조": ["精算および支払", "客室利用料金は後日精算します。", "支払時期と支払主体が不明確なため、精算遅延や未収金紛争が発生する可能性があります。", "毎月末に利用実績を締め、翌月15日までにバイヤーがセルラーへ支払うと明記してください。"],
      "제8조": ["紛争解決", "本契約に関する紛争は釜山地方裁判所を第一審の管轄裁判所とします。"],
    },
    "gwangan-seabreeze": {
      "제1조": ["契約の目的", "セルラーがバイヤーに広安里オーシャンビュー客室を供給する条件を定めます。"],
      "제2조": ["供給期間および数量", "2026年6月15日から9月15日まで、平日・週末とも最大40室を供給します。"],
      "제3조": ["精算および支払", "毎月末締め後、翌々月（約60日後）の15日に支払います。", "60日の精算周期は一般的な30日より長く、バイヤーの運転資金負担が増える可能性があります。", "翌月15日に短縮するか、60日を維持する場合は早期精算割引を追加してください。"],
      "제4조": ["取消およびノーショー", "チェックイン5日前まで無料取消とし、ノーショー時は1泊料金の80％を請求します。"],
    },
    "marina-yacht-tour": {
      "제1조": ["契約の目的", "ヨット・サンセットツアーの座席供給条件を定めます。"],
      "제2조": ["安全事故の賠償責任", "ツアー中の安全事故について利用者に故意・過失がない場合、セルラーが責任を負いますが、賠償限度は1人500万ウォンとします。", "重大事故ではバイヤーが追加賠償責任を負う可能性があります。", "セルラーの賠償責任保険加入を条件とし、保険限度内では別途上限を設けないよう調整してください。"],
      "제3조": ["悪天候時の対応", "悪天候で運航が中止された場合、全額返金または日程変更を行います。"],
    },
    "songjeong-surf": {
      "제1조": ["契約の目的", "サーフィンレッスン商品の供給条件を定めます。"],
      "제2조": ["取消方針", "利用1日前まで無料で取り消せますが、当日取消はレッスン料金全額を請求します。", "無料取消期限が短く、団体予約変更時の負担が大きくなる可能性があります。", "10名以上の団体予約は無料取消期限を利用3日前まで延長することを推奨します。"],
    },
    "busan-city-tour": {
      "제1조": ["契約の目的", "釜山シティツアー商品の供給条件を定めます。"],
      "제2조": ["料金構成", "繁忙期・閑散期の料金を分けて適用し、詳細料金表を添付します。"],
    },
    "gijang-glamping": {
      "제1조": ["契約の目的", "オーシャンビューグランピングの供給条件を定めます。"],
      "제2조": ["取消および精算", "チェックイン7日前まで無料取消とし、精算金は翌月15日に支払います。"],
    },
  },
  zh: {
    "ocean-stay-2026-summer": {
      "제1조": ["合同目的", "本合同旨在规定卖方（海云台海洋住宿）向买方供应2026年夏季旺季客房，并由买方进行销售和分销所需的条件。"],
      "제2조": ["供应期间及数量", "供应期为2026年7月1日至8月31日，周末（周五、周六）最多供应30间客房。工作日客房可经双方协商追加。"],
      "제3조": ["供应单价", "客房供应价格为每间145,000韩元，不含增值税。"],
      "제4조": ["取消与退款", "买方可根据需要免费取消预订。", "未规定免费取消期限及后续手续费标准，卖方可能需要承担直至入住前的取消风险。", "建议明确入住7天前可免费取消，此后收取一晚房费的50％。"],
      "제5조": ["未到店处理", "未另行规定未到店情况的处理标准。", "未规定客人未到店时的收费标准，双方可能对结算范围产生争议。", "建议明确未到店时收取相应客房一晚房费的100％。"],
      "제6조": ["结算与支付", "客房使用费用将在以后结算。", "付款时间和付款主体不明确，可能造成结算延迟或欠款争议。", "建议每月底结算使用记录，并规定买方于次月15日前向卖方付款。"],
      "제8조": ["争议解决", "因本合同发生争议时，釜山地方法院为一审管辖法院。"],
    },
    "gwangan-seabreeze": {
      "제1조": ["合同目的", "规定卖方向买方供应广安里海景客房的条件。"],
      "제2조": ["供应期间及数量", "2026年6月15日至9月15日，工作日和周末最多供应40间客房。"],
      "제3조": ["结算与支付", "每月底结算后，于隔月15日付款，周期约为60天。", "60天的结算周期长于常见的30天，可能增加买方的营运资金负担。", "建议缩短至次月15日，或在保留60天周期时增加提前结算折扣。"],
      "제4조": ["取消与未到店", "入住5天前可免费取消，未到店时收取一晚房费的80％。"],
    },
    "marina-yacht-tour": {
      "제1조": ["合同目的", "规定游艇日落之旅座位的供应条件。"],
      "제2조": ["安全事故赔偿责任", "游览期间发生安全事故且游客无故意或过失时，由卖方承担责任，但每人赔偿上限为500万韩元。", "如发生重大事故，买方可能承担额外赔偿责任。", "建议要求卖方投保营业责任保险，并在保险范围内不另设赔偿上限。"],
      "제3조": ["恶劣天气处理", "因恶劣天气取消航程时，将全额退款或调整日期。"],
    },
    "songjeong-surf": {
      "제1조": ["合同目的", "规定冲浪课程商品的供应条件。"],
      "제2조": ["取消政策", "使用前1天可免费取消，当天取消时收取全部课程费用。", "免费取消期限较短，团体预订变更时买方可能承担较高费用。", "建议10人以上团体预订的免费取消期限放宽至使用前3天。"],
    },
    "busan-city-tour": {
      "제1조": ["合同目的", "规定釜山城市旅游产品的供应条件。"],
      "제2조": ["价格构成", "旺季和淡季价格分别适用，详细价格表作为附件。"],
    },
    "gijang-glamping": {
      "제1조": ["合同目的", "规定海景豪华露营单元的供应条件。"],
      "제2조": ["取消与结算", "入住7天前可免费取消，款项于次月15日支付。"],
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
  const contract = getContract(id);
  const [activeClause, setActiveClause] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [documentLanguage, setDocumentLanguage] = useState<DocLang>("ko");

  if (!contract) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">
        {t("explore.empty")}
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
      navigate(`/buyer/explore/${contract.id}/request`);
    } else {
      navigate(`/buyer/explore/${contract.id}/revise`);
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
