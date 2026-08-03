import {
  useEffect,
  useMemo,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Download,
  FileCheck2,
  FilePenLine,
  Languages,
  Lightbulb,
  LogOut,
  Sparkles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useApp } from "../../context/AppContext";
import { useExploreCtx } from "../../hooks/useExploreCtx";
import {
  analyzePublicContract,
  friendlyApiError,
  getPublicContractPreview,
  getPublicListing,
  getPublicSourceDocumentUrl,
  translatePublicContract,
  type ContractAssistantFinding,
  type ContractTranslation,
  type ContractTranslationLocale,
  type PublicListingDetail,
} from "../../lib/api";

type DocumentLanguage = "ko-KR" | ContractTranslationLocale;

const DOCUMENT_LANGUAGES: Array<{
  value: DocumentLanguage;
  label: string;
}> = [
  { value: "ko-KR", label: "한국어 원문" },
  { value: "en-US", label: "English" },
  { value: "ja-JP", label: "日本語" },
  { value: "zh-CN", label: "中文" },
];

type DisplayFinding = {
  clauseId: string;
  severity: "high" | "medium" | "low";
  explanation: string;
  suggestedText: string | null;
};

function dateLabel(value: string | null): string {
  return value ? value.replace(/-/g, ".") : "정보 없음";
}

function clauseNumberLabel(
  language: DocumentLanguage,
  index: number,
): string {
  if (language === "ko-KR") return `제${index + 1}조`;
  if (language === "en-US") return `Article ${index + 1}`;
  return `第${index + 1}条`;
}

function severityLabel(severity: DisplayFinding["severity"]): string {
  if (severity === "high") return "높은 주의";
  if (severity === "medium") return "주의";
  return "참고";
}

export function ContractDocumentPage() {
  const { lang, t } = useApp();
  const { base, isGuest } = useExploreCtx();
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [language, setLanguage] =
    useState<DocumentLanguage>("ko-KR");
  const [listing, setListing] =
    useState<PublicListingDetail | null>(null);
  const [preview, setPreview] =
    useState<Awaited<ReturnType<typeof getPublicContractPreview>> | null>(
      null,
    );
  const [translations, setTranslations] = useState<
    Partial<Record<ContractTranslationLocale, ContractTranslation>>
  >({});
  const [sourcePdfUrl, setSourcePdfUrl] = useState<string | null>(null);
  const [assistantFindings, setAssistantFindings] = useState<
    ContractAssistantFinding[] | null
  >(null);
  const [translationLoading, setTranslationLoading] = useState(false);
  const [translationError, setTranslationError] = useState<string | null>(
    null,
  );
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const selectedLocale: DocumentLanguage = lang === "ko" ? "ko-KR" : lang === "en" ? "en-US" : lang === "ja" ? "ja-JP" : "zh-CN";

  // The global language selector also controls full-contract translation.
  // Users can still choose a different document language using the local buttons.
  useEffect(() => {
    setLanguage(selectedLocale);
  }, [selectedLocale]);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      setError("계약서 식별자가 없습니다.");
      return;
    }

    let active = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      setListing(null);
      setPreview(null);
      setLanguage(selectedLocale);
      setTranslations({});
      setAssistantFindings(null);
      setAssistantError(null);
      setTranslationError(null);

      try {
        const nextListing = await getPublicListing(id, "ko-KR");

        if (!active) return;

        setListing(nextListing);
        setLoading(false);

        try {
          const nextPreview = await getPublicContractPreview(id, "ko-KR");
          if (active) setPreview(nextPreview);
        } catch {
          // 저장된 AI 분석이 없어도 계약서 원문은 계속 표시한다.
          if (active) setPreview(null);
        }
      } catch (reason: unknown) {
        if (!active) return;
        setError(friendlyApiError(reason));
        setLoading(false);
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, [id, selectedLocale]);

  useEffect(() => {
    setSourcePdfUrl(null);

    if (!id || isGuest) return;

    let active = true;

    void getPublicSourceDocumentUrl(id)
      .then((result) => {
        if (active) setSourcePdfUrl(result.download_url);
      })
      .catch(() => {
        if (active) setSourcePdfUrl(null);
      });

    return () => {
      active = false;
    };
  }, [id, isGuest]);

  useEffect(() => {
    if (!listing || isGuest) {
      setAssistantLoading(false);
      return;
    }

    let active = true;

    setAssistantLoading(true);
    setAssistantError(null);

    void analyzePublicContract(listing)
      .then((result) => {
        if (active) setAssistantFindings(result.findings);
      })
      .catch((reason: unknown) => {
        if (active) setAssistantError(friendlyApiError(reason));
      })
      .finally(() => {
        if (active) setAssistantLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isGuest, listing]);

  useEffect(() => {
    if (
      language === "ko-KR" ||
      !listing ||
      translations[language]
    ) {
      setTranslationLoading(false);
      return;
    }

    let active = true;

    setTranslationLoading(true);
    setTranslationError(null);

    void translatePublicContract(listing, language)
      .then((translated) => {
        if (!active) return;

        setTranslations((current) => ({
          ...current,
          [language]: translated,
        }));
      })
      .catch((reason: unknown) => {
        if (active) setTranslationError(friendlyApiError(reason));
      })
      .finally(() => {
        if (active) setTranslationLoading(false);
      });

    return () => {
      active = false;
    };
  }, [language, listing, translations]);

  const translation =
    language === "ko-KR"
      ? null
      : translations[language] ?? null;

  const findings = useMemo<DisplayFinding[]>(() => {
    if (assistantFindings) {
      return assistantFindings.map((finding) => ({
        clauseId: finding.clause_id,
        severity: finding.severity,
        explanation: finding.explanation,
        suggestedText: finding.suggested_text,
      }));
    }

    return (preview?.findings ?? []).flatMap((finding) => {
      if (!finding.clause_id || finding.severity === "none") {
        return [];
      }

      return [{
        clauseId: finding.clause_id,
        severity: finding.severity,
        explanation: finding.explanation,
        suggestedText: finding.suggested_text || null,
      }];
    });
  }, [assistantFindings, preview]);

  const clauses = useMemo(() => {
    if (!listing) return [];

    return listing.clauses.map((clause) => {
      const translated = translation?.clauses.find(
        (item) => item.id === clause.id,
      );
      const finding = findings.find(
        (item) => item.clauseId === clause.id,
      );

      return {
        ...clause,
        title: translated?.title ?? clause.title,
        body: translated?.body ?? clause.body,
        finding,
      };
    });
  }, [findings, listing, translation]);

  const displayTitle = translation?.title ?? listing?.title ?? "";

  if (loading) {
    return (
      <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">
        계약서를 불러오는 중입니다…
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">
        {error ?? t("explore.empty")}
      </div>
    );
  }

  const downloadDocument = () => {
    const notice =
      language === "ko-KR"
        ? ""
        : "AI 번역본입니다. 한국어 원문과 함께 확인해 주세요.";

    const content = [
      displayTitle,
      listing.seller.name,
      notice,
      "",
      ...clauses.map(
        (clause, index) =>
          `${clauseNumberLabel(language, index)} ${clause.title}\n${clause.body}`,
      ),
    ].join("\n\n");

    const url = URL.createObjectURL(
      new Blob([content], {
        type: "text/plain;charset=utf-8",
      }),
    );

    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${displayTitle}-${language}.txt`;
    anchor.click();

    URL.revokeObjectURL(url);
    toast.success("계약서 다운로드를 시작했습니다.");
  };

  const downloadSourcePdf = async (
    event: ReactMouseEvent<HTMLAnchorElement>,
  ) => {
    event.preventDefault();

    if (!sourcePdfUrl) return;

    try {
      const response = await fetch(sourcePdfUrl);

      if (!response.ok) {
        throw new Error("PDF download failed");
      }

      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");

      anchor.href = url;
      anchor.download = `${listing.title}-원문.pdf`;
      anchor.click();

      URL.revokeObjectURL(url);
      toast.success("계약서 원문 다운로드를 시작했습니다.");
    } catch {
      toast.error(
        "계약서 원문을 다운로드하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    }
  };

  const jumpToClause = (clauseId: string) => {
    document
      .getElementById(`clause-${clauseId}`)
      ?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
  };

  const handleRequest = (asIs: boolean) => {
    if (isGuest) {
      toast.info("계약 요청은 로그인 후 이용할 수 있습니다.");
      navigate("/login");
      return;
    }

    const path = asIs ? "request" : "revise";
    navigate(`${base}/${listing.id}/${path}${location.search}`);
  };

  return (
    <div>
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 gap-1.5 whitespace-nowrap"
        onClick={() =>
          navigate(`${base}/${listing.id}${location.search}`)
        }
      >
        <ArrowLeft className="size-4" />
        {t("summary.backToList")}
      </Button>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h1 style={{ color: "var(--navy)" }}>
          {displayTitle}
        </h1>
        <VersionBadge version="v1" />
      </div>

      <p className="mb-5 text-sm text-muted-foreground">
        {listing.seller.name} ·{" "}
        {dateLabel(listing.availability.start_date)} ~{" "}
        {dateLabel(listing.availability.end_date)}
      </p>

      <div className="mb-5 rounded-xl border border-border bg-card p-4">
        <ContractStepper current={1} />
      </div>

      {sourcePdfUrl && (
        <section className="mb-5 overflow-hidden rounded-xl border border-border bg-card">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-4">
            <div>
              <h3 style={{ color: "var(--navy)" }}>
                계약서 원문 PDF
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                셀러가 등록한 원본 PDF입니다.
              </p>
            </div>

            <a
              href={sourcePdfUrl}
              onClick={(event) => void downloadSourcePdf(event)}
              className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium hover:bg-muted"
            >
              <Download className="size-4" />
              PDF 다운로드
            </a>
          </div>

          <iframe
            title="계약서 원문 PDF"
            src={sourcePdfUrl}
            className="h-[75vh] min-h-[560px] w-full"
          />
        </section>
      )}

      <div className="mb-5 flex flex-col items-stretch justify-between gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <Languages
            className="size-5"
            style={{ color: "var(--ocean)" }}
          />
          <div>
            <div
              className="font-semibold"
              style={{ color: "var(--navy)" }}
            >
              계약서 언어
            </div>
            <div className="text-xs text-muted-foreground">
              언어를 선택하면 계약서 본문을 AI로 번역합니다.
            </div>
          </div>
        </div>

        <div
          className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap"
          role="group"
          aria-label="계약서 번역 언어 선택"
        >
          {DOCUMENT_LANGUAGES.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={
                language === option.value
                  ? "default"
                  : "outline"
              }
              disabled={
                translationLoading &&
                language !== option.value
              }
              className="whitespace-nowrap"
              onClick={() => setLanguage(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
      </div>

      {language !== "ko-KR" && (
        <div className="mb-5 rounded-lg border border-[var(--ocean)] bg-[var(--info-soft)] p-3 text-sm">
          {translationLoading
            ? "Solar Pro 3가 계약서 원문을 번역하고 있습니다…"
            : translationError
              ? `AI 번역에 실패해 한국어 원문을 표시합니다. ${translationError}`
              : "AI 번역본입니다. 한국어 원문과 함께 확인해 주세요."}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-10 xl:gap-6">
        <div className="xl:col-span-7">
          <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-4">
              <h2
                className="font-semibold"
                style={{ color: "var(--navy)" }}
              >
                계약서 원문
              </h2>

              <div className="flex items-center gap-1.5">
                <Badge
                  variant="outline"
                  className="gap-1 whitespace-nowrap"
                >
                  <Languages className="size-3.5" />
                  {
                    DOCUMENT_LANGUAGES.find(
                      (item) => item.value === language,
                    )?.label
                  }
                </Badge>

                <Button
                  variant="outline"
                  size="sm"
                  aria-label="축소"
                  onClick={() =>
                    setZoom((value) => Math.max(85, value - 5))
                  }
                >
                  <ZoomOut className="size-4" />
                </Button>

                <span className="w-12 text-center text-xs text-muted-foreground">
                  {zoom}%
                </span>

                <Button
                  variant="outline"
                  size="sm"
                  aria-label="확대"
                  onClick={() =>
                    setZoom((value) => Math.min(120, value + 5))
                  }
                >
                  <ZoomIn className="size-4" />
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1 whitespace-nowrap"
                  onClick={downloadDocument}
                >
                  <Download className="size-4" />
                  다운로드
                </Button>
              </div>
            </div>

            <div
              className="space-y-5"
              style={{ fontSize: `${zoom / 100}em` }}
            >
              {clauses.map((clause, index) => (
                <section
                  key={clause.id}
                  id={`clause-${clause.id}`}
                  className="scroll-mt-6 rounded-lg border border-border p-4"
                >
                  <h3 className="flex items-center gap-2 text-base">
                    <span style={{ color: "var(--ocean)" }}>
                      {clauseNumberLabel(language, index)}
                    </span>

                    <span>{clause.title}</span>

                    {clause.finding && (
                      <Badge
                        className="border-transparent"
                        style={{
                          background: "var(--coral-soft)",
                          color: "var(--coral)",
                        }}
                      >
                        <AlertTriangle className="mr-1 size-3" />
                        확인 필요
                      </Badge>
                    )}
                  </h3>

                  <p className="mt-2 leading-7">
                    {clause.body}
                  </p>
                </section>
              ))}
            </div>
          </div>
        </div>

        <aside className="xl:col-span-3">
          <div className="sticky top-20 rounded-xl border border-[var(--ocean)] bg-[var(--info-soft)] p-5">
            <div
              className="flex items-center gap-1.5 font-semibold"
              style={{ color: "var(--ocean)" }}
            >
              <Sparkles className="size-4" />
              AI 계약 비서
            </div>

            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              계약서를 바이어 관점에서 분석했습니다.
            </p>

            {assistantLoading ? (
              <p className="mt-4 text-sm leading-6">
                Solar Pro 3가 계약 조항을 검토하고 있습니다…
              </p>
            ) : (
              <>
                <div className="mt-4 flex items-center gap-1.5 text-sm font-semibold text-[var(--coral)]">
                  <AlertTriangle className="size-4" />
                  확인 필요 조항 {findings.length}개
                </div>

                <div className="mt-3 flex max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1">
                  {findings.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      확인이 필요한 조항이 없습니다.
                    </p>
                  )}

                  {findings.map((finding) => {
                    const clause = clauses.find(
                      (item) => item.id === finding.clauseId,
                    );

                    return (
                      <button
                        key={`${finding.clauseId}-${finding.severity}`}
                        type="button"
                        onClick={() =>
                          jumpToClause(finding.clauseId)
                        }
                        className="rounded-lg border bg-card p-3 text-left transition-colors hover:border-[var(--coral)]"
                      >
                        <div className="flex items-center gap-1.5 text-sm font-semibold text-[var(--coral)]">
                          <Lightbulb className="size-3.5" />
                          {clause?.title ?? "확인 필요 조항"}
                        </div>

                        <div className="mt-1 text-xs font-semibold text-muted-foreground">
                          {severityLabel(finding.severity)}
                        </div>

                        <p className="mt-2 text-sm leading-6">
                          {finding.explanation}
                        </p>

                        {finding.suggestedText && (
                          <div className="mt-3 rounded-md bg-[var(--info-soft)] p-2">
                            <div className="flex items-center gap-1 text-xs font-semibold text-[var(--teal)]">
                              <Lightbulb className="size-3.5" />
                              AI 추천 문구
                            </div>
                            <p className="mt-1 text-xs leading-5">
                              {finding.suggestedText}
                            </p>
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            {assistantError && (
              <p className="mt-3 text-xs leading-5 text-destructive">
                실시간 AI 분석에 실패했습니다. 저장된 분석 결과를 표시합니다.
                <br />
                {assistantError}
              </p>
            )}

            <p className="mt-4 border-t border-border pt-3 text-xs leading-5 text-muted-foreground">
              AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이 아닙니다.
            </p>
          </div>
        </aside>
      </div>

      <div className="mt-6 flex flex-wrap justify-end gap-2 rounded-xl border border-border bg-card p-4">
        <Button
          variant="outline"
          onClick={() => handleRequest(true)}
        >
          <FileCheck2 className="mr-1 size-4" />
          조건 그대로 요청
        </Button>

        <Button
          style={{ background: "var(--navy)" }}
          onClick={() => handleRequest(false)}
        >
          <FilePenLine className="mr-1 size-4" />
          수정 요청
        </Button>

        <Button
          variant="ghost"
          onClick={() =>
            navigate(`${base}/${listing.id}${location.search}`)
          }
        >
          <LogOut className="mr-1 size-4" />
          나가기
        </Button>
      </div>
    </div>
  );
}
