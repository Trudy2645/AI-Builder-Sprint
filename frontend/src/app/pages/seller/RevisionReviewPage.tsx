import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Check,
  Eye,
  GitBranch,
  Send,
  X,
} from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ContractStepper } from "../../components/contract/ContractStepper";
import {
  ReviewClauseCard,
  emptyDecision,
  type Decision,
  type ReceivedRevision,
} from "../../components/received/ReviewClauseCard";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { useApp } from "../../context/AppContext";
import {
  decideRevisionRequest,
  friendlyApiError,
  generateRevisionGuidance,
  getContractDetail,
  getRevisionRequest,
  patchRevisionItem,
  type ContractDetail,
  type RevisionGuidanceItem,
  type RevisionRequestResponse,
} from "../../lib/api";

type RevisionItem =
  RevisionRequestResponse["items"][number];

function formatDate(value: string | null | undefined): string {
  return value
    ? value.slice(0, 10).replace(/-/g, ".")
    : "정보 없음";
}

function formatAmount(
  amount: number | null,
  currency: string | null,
): string {
  if (amount === null || amount === undefined) {
    return "계약 조건에서 확인";
  }

  if (currency === "KRW") {
    return `${amount.toLocaleString("ko-KR")}원`;
  }

  return `${amount.toLocaleString("ko-KR")} ${currency ?? ""}`.trim();
}

function findContractClause(
  contract: ContractDetail,
  item: RevisionItem,
) {
  const directClause = item.clause_id
    ? contract.current_version.clauses.find(
        (clause) => clause.id === item.clause_id,
      )
    : undefined;

  if (directClause) return directClause;

  if (item.request_type === "add") {
    return undefined;
  }

  return contract.current_version.clauses[
    item.item_order - 1
  ];
}

export function RevisionReviewPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();

  const [revision, setRevision] =
    useState<RevisionRequestResponse | null>(null);
  const [contract, setContract] =
    useState<ContractDetail | null>(null);
  const [decisions, setDecisions] = useState<
    Record<string, Decision>
  >({});
  const [guidance, setGuidance] = useState<
    Record<string, RevisionGuidanceItem>
  >({});
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [guidanceLoading, setGuidanceLoading] =
    useState(true);
  const [guidanceError, setGuidanceError] =
    useState<string | null>(null);
  const [loadError, setLoadError] =
    useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      setLoadError("수정 요청 식별자가 없습니다.");
      return;
    }

    let active = true;

    const load = async () => {
      setLoading(true);
      setLoadError(null);
      setGuidanceError(null);

      try {
        const nextRevision = await getRevisionRequest(id);
        const nextContract = await getContractDetail(
          nextRevision.contract_id,
        );

        if (!active) return;

        setRevision(nextRevision);
        setContract(nextContract);
        setDecisions(
          Object.fromEntries(
            nextRevision.items.map((item) => [
              item.id,
              emptyDecision(),
            ]),
          ),
        );
        setLoading(false);

        if (nextRevision.status !== "sent") {
          setGuidanceLoading(false);
          return;
        }

        setGuidanceLoading(true);

        try {
          const result = await generateRevisionGuidance(
            nextRevision.items.map((item) => {
              const clause = findContractClause(
                nextContract,
                item,
              );

              const requestedText =
                item.requested_text ??
                (item.request_type === "delete"
                  ? "이 조항을 삭제해 달라는 요청"
                  : item.request_type === "add"
                    ? "새 조항을 추가해 달라는 요청"
                    : "수정 문구가 입력되지 않았습니다.");

              return {
                id: item.id,
                clause_title:
                  clause?.title ??
                  (item.request_type === "add"
                    ? "추가 조항"
                    : "확인되지 않은 조항"),
                original_text:
                  clause?.body ?? "기존 조항 없음",
                requested_text: requestedText,
                reason:
                  item.reason ||
                  "바이어가 계약 조건 수정을 요청했습니다.",
              };
            }),
          );

          if (!active) return;

          setGuidance(
            Object.fromEntries(
              result.items.map((item) => [
                item.id,
                item,
              ]),
            ),
          );
        } catch (error) {
          if (active) {
            setGuidanceError(friendlyApiError(error));
          }
        } finally {
          if (active) setGuidanceLoading(false);
        }
      } catch (error) {
        if (!active) return;

        setLoadError(friendlyApiError(error));
        setLoading(false);
        setGuidanceLoading(false);
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, [id]);

  const rows = useMemo<ReceivedRevision[]>(() => {
    if (!revision || !contract) return [];

    return revision.items.map((item) => {
      const clause = findContractClause(contract, item);

      const requested =
        item.requested_text ??
        (item.request_type === "delete"
          ? "조항 삭제 요청"
          : item.request_type === "add"
            ? "새 조항 추가 요청"
            : "수정 문구 없음");

      return {
        id: item.id,
        clauseNo: clause
          ? `제${clause.clause_order}조`
          : item.request_type === "add"
            ? "추가 조항"
            : `항목 ${item.item_order}`,
        clauseTitle:
          clause?.title ??
          (item.request_type === "add"
            ? "추가 조항"
            : "확인되지 않은 조항"),
        original: clause?.body ?? "기존 조항 없음",
        requested,
        reason:
          item.reason ||
          "바이어가 계약 조건 수정을 요청했습니다.",
        aiImpact: guidance[item.id]?.impact ?? "",
        aiRecommend: guidance[item.id]?.recommendation ?? "",
        aiRejectReason:
          guidance[item.id]?.rejection_reason ?? "",
        aiLoading: guidanceLoading,
        aiError: guidanceError,
      };
    });
  }, [
    contract,
    guidance,
    guidanceError,
    guidanceLoading,
    revision,
  ]);

  const total = rows.length;

  const decidedCount = Object.values(decisions).filter(
    (decision) => decision.kind,
  ).length;

  const allDecided =
    total > 0 && decidedCount === total;

  const counts = Object.values(decisions).reduce<{
    accept: number;
    reject: number;
    counter: number;
  }>(
    (result, decision) => {
      if (decision.kind) {
        result[decision.kind] += 1;
      }
      return result;
    },
    {
      accept: 0,
      reject: 0,
      counter: 0,
    },
  );

  if (loading) {
    return (
      <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">
        수정 요청을 불러오는 중입니다…
      </div>
    );
  }

  if (!revision || !contract) {
    return (
      <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">
        {loadError ?? "수정 요청을 찾을 수 없습니다."}
      </div>
    );
  }

  if (revision.status !== "sent") {
    const statusLabel =
      revision.status === "accepted"
        ? "수락 완료"
        : revision.status === "rejected"
          ? "거절 완료"
          : revision.status === "countered"
            ? "대안 전송 완료"
            : revision.status === "partially_accepted"
              ? "일부 수락 완료"
              : "처리 완료";

    if (revision.status === "countered") {
      return (
        <div className="mx-auto max-w-[820px]">
          <Button
            variant="ghost"
            size="sm"
            className="mb-4 gap-1.5 whitespace-nowrap"
            onClick={() => navigate("/seller/negotiating")}
          >
            <ArrowLeft className="size-4" />
            협상 중인 계약
          </Button>
          <PageHeader
            title="셀러 대안 전송 완료"
            description={`${contract.listing_title} · 바이어의 응답을 기다리는 중입니다.`}
          />
          <div className="mb-5 rounded-xl border border-[var(--ocean)] bg-[var(--info-soft)] p-5">
            <p className="font-semibold" style={{ color: "var(--navy)" }}>
              셀러가 대안 조건을 보냈습니다.
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              바이어가 대안을 수락하거나 추가 의견을 보내면 협상이 이어집니다.
            </p>
          </div>
          <div className="space-y-3">
            {revision.items.map((item) => (
              <div key={item.id} className="rounded-xl border border-border bg-card p-5">
                <div className="text-sm font-semibold" style={{ color: "var(--navy)" }}>
                  요청 항목 {item.item_order}
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  바이어 요청: {item.requested_text ?? item.reason}
                </p>
                <div className="mt-3 rounded-lg border border-[var(--ocean)] bg-[var(--info-soft)] p-3 text-sm leading-6">
                  <div className="mb-1 text-xs font-semibold" style={{ color: "var(--ocean)" }}>
                    셀러 대안
                  </div>
                  {item.counter_text ?? item.seller_reason ?? "대안 조건을 확인할 수 없습니다."}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-6 flex justify-end rounded-xl border border-border bg-card p-4">
            <Button variant="outline" onClick={() => navigate("/seller/negotiating")}>
              협상 중인 계약으로 돌아가기
            </Button>
          </div>
        </div>
      );
    }

    return (
      <div className="mx-auto max-w-[720px] rounded-xl border border-border bg-card p-10 text-center">
        <h1 className="text-xl font-semibold">
          이미 처리된 수정 요청입니다
        </h1>
        <p className="mt-2 text-muted-foreground">
          현재 상태: {statusLabel}
        </p>
        <Button
          className="mt-6"
          onClick={() => navigate("/seller/received")}
        >
          받은 요청으로 돌아가기
        </Button>
      </div>
    );
  }

  const buyerName =
    contract.parties.find(
      (party) => party.role === "buyer",
    )?.name ?? "바이어";

  const period = `${formatDate(
    contract.terms.start_date,
  )} ~ ${formatDate(contract.terms.end_date)}`;

  const estimatedAmount = formatAmount(
    contract.terms.amount_minor,
    contract.terms.currency,
  );

  const updateDecision = (
    revisionId: string,
    decision: Decision,
  ) => {
    setDecisions((previous) => ({
      ...previous,
      [revisionId]: decision,
    }));
  };

  const responseText = (
    revisionId: string,
    original: string,
    requested: string,
  ) => {
    const decision =
      decisions[revisionId] ?? emptyDecision();

    if (decision.kind === "accept") {
      return requested;
    }

    if (decision.kind === "counter") {
      return (
        decision.counterText.trim() ||
        t("rvw.pending")
      );
    }

    if (decision.kind === "reject") {
      return original;
    }

    return t("rvw.pending");
  };

  const validateDecisions = (): boolean => {
    if (!allDecided) {
      toast.error(t("rvw.needAll"));
      return false;
    }

    const missingCounter = rows.some((row) => {
      const decision = decisions[row.id];

      return (
        decision?.kind === "counter" &&
        !decision.counterText.trim()
      );
    });

    if (missingCounter) {
      toast.error(t("rvw.needCounterText"));
      return false;
    }

    return true;
  };

  const openPreview = () => {
    if (validateDecisions()) {
      setPreviewOpen(true);
    }
  };

  const send = async () => {
    if (!validateDecisions()) return;

    setSubmitting(true);

    try {
      const current = await getRevisionRequest(
        revision.id,
      );

      if (current.status !== "sent") {
        setRevision(current);
        toast.error("이미 처리된 수정 요청입니다.");
        return;
      }

      let latest = current;

      for (const item of current.items) {
        const decision = decisions[item.id];

        if (!decision?.kind) {
          throw new Error("모든 요청 조항을 판단해 주세요.");
        }

        latest = await patchRevisionItem(
          current.id,
          item.id,
          {
            decision:
              decision.kind === "accept"
                ? "accepted"
                : decision.kind === "reject"
                  ? "rejected"
                  : "countered",
            seller_reason:
              [
                decision.counterReason,
                decision.message,
              ]
                .filter(Boolean)
                .join("\n") || undefined,
            counter_text:
              decision.kind === "counter"
                ? decision.counterText.trim()
                : undefined,
          },
        );
      }

      await decideRevisionRequest(latest.id, {
        seller_message:
          "셀러가 수정 요청 항목을 검토하고 응답했습니다.",
      });

      toast.success(t("rvw.sent"));
      navigate("/seller/negotiating");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[960px]">
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 gap-1.5 whitespace-nowrap"
        onClick={() => navigate("/seller/received")}
      >
        <ArrowLeft className="size-4" />
        {t("recv.title")}
      </Button>

      <PageHeader
        title={t("rvw.title")}
        description={`${t("rvw.from")}: ${buyerName} · ${contract.listing_title}`}
      />

      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={3} />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
        <div>
          <div className="text-xs text-muted-foreground">
            요청일
          </div>
          <div className="mt-1 font-semibold">
            {formatDate(revision.created_at)}
          </div>
        </div>

        <div>
          <div className="text-xs text-muted-foreground">
            계약 기간
          </div>
          <div className="mt-1 font-semibold">
            {period}
          </div>
        </div>

        <div>
          <div className="text-xs text-muted-foreground">
            예상 계약 금액
          </div>
          <div className="mt-1 font-semibold">
            {estimatedAmount}
          </div>
        </div>

        <div>
          <div className="text-xs text-muted-foreground">
            현재 버전
          </div>
          <div
            className="mt-1 font-semibold"
            style={{ color: "var(--ocean)" }}
          >
            v{contract.current_version.version_no}
          </div>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-3">
        <span
          className="whitespace-nowrap"
          style={{
            fontWeight: 600,
            color: "var(--navy)",
          }}
        >
          {t("rvw.progress")} {decidedCount}
          {t("rvw.progressOf").replace(
            "{total}",
            String(total),
          )}
        </span>

        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${
                total > 0
                  ? (decidedCount / total) * 100
                  : 0
              }%`,
              background: allDecided
                ? "var(--success)"
                : "var(--ocean)",
            }}
          />
        </div>

        <div className="flex items-center gap-1.5 whitespace-nowrap">
          <Badge
            className="gap-1 border-transparent"
            style={{
              background: "var(--success-soft)",
              color: "var(--success)",
            }}
          >
            <Check className="size-3" />
            {counts.accept}
          </Badge>

          <Badge
            className="gap-1 border-transparent"
            style={{
              background: "var(--coral-soft)",
              color: "var(--coral)",
            }}
          >
            <X className="size-3" />
            {counts.reject}
          </Badge>

          <Badge
            className="gap-1 border-transparent"
            style={{
              background: "var(--info-soft)",
              color: "var(--ocean)",
            }}
          >
            <GitBranch className="size-3" />
            {counts.counter}
          </Badge>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {rows.map((row, index) => (
          <ReviewClauseCard
            key={row.id}
            index={index}
            revision={row}
            decision={
              decisions[row.id] ?? emptyDecision()
            }
            onChange={(decision) =>
              updateDecision(row.id, decision)
            }
          />
        ))}
      </div>

      <div className="mt-6 flex justify-end gap-2 rounded-xl border border-border bg-card p-4">
        <Button
          variant="outline"
          className="gap-1.5 whitespace-nowrap"
          onClick={openPreview}
        >
          <Eye className="size-4" />
          미리보기
        </Button>

        <Button
          className="gap-1.5 whitespace-nowrap"
          style={{ background: "var(--navy)" }}
          disabled={submitting || !allDecided}
          onClick={() => void send()}
        >
          <Send className="size-4" />
          {t("rvw.send")}
        </Button>
      </div>

      <Dialog
        open={previewOpen}
        onOpenChange={setPreviewOpen}
      >
        <DialogContent className="max-h-[90vh] w-[calc(100vw-2rem)] max-w-[860px] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {t("rvw.previewTitle")}
            </DialogTitle>
            <DialogDescription>
              {t("rvw.previewDesc")}
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div
              className="rounded-lg p-3 text-center"
              style={{ background: "var(--success-soft)" }}
            >
              <div
                style={{
                  fontSize: "22px",
                  fontWeight: 700,
                  color: "var(--success)",
                }}
              >
                {counts.accept}
              </div>
              <div className="text-xs text-[var(--success)]">
                {t("rvw.sumAccepted")}
              </div>
            </div>

            <div
              className="rounded-lg p-3 text-center"
              style={{ background: "var(--coral-soft)" }}
            >
              <div
                style={{
                  fontSize: "22px",
                  fontWeight: 700,
                  color: "var(--coral)",
                }}
              >
                {counts.reject}
              </div>
              <div className="text-xs text-[var(--coral)]">
                {t("rvw.sumRejected")}
              </div>
            </div>

            <div
              className="rounded-lg p-3 text-center"
              style={{ background: "var(--info-soft)" }}
            >
              <div
                style={{
                  fontSize: "22px",
                  fontWeight: 700,
                  color: "var(--ocean)",
                }}
              >
                {counts.counter}
              </div>
              <div className="text-xs text-[var(--ocean)]">
                {t("rvw.sumCountered")}
              </div>
            </div>
          </div>

          <div className="max-h-[50vh] overflow-auto rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    {t("rvw.cmp.clause")}
                  </TableHead>
                  <TableHead>
                    {t("rvw.cmp.original")}
                  </TableHead>
                  <TableHead>
                    {t("rvw.cmp.requested")}
                  </TableHead>
                  <TableHead>
                    {t("rvw.cmp.response")}
                  </TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {rows.map((row) => {
                  const decision =
                    decisions[row.id] ?? emptyDecision();

                  const responseColor =
                    decision.kind === "accept"
                      ? "var(--success)"
                      : decision.kind === "reject"
                        ? "var(--coral)"
                        : "var(--ocean)";

                  const response =
                    decision.kind === "accept"
                      ? t("rvw.accepted")
                      : decision.kind === "reject"
                        ? t("rvw.rejected")
                        : decision.kind === "counter"
                          ? t("rvw.countered")
                          : t("rvw.pending");

                  return (
                    <TableRow key={row.id}>
                      <TableCell className="align-top whitespace-nowrap">
                        <div
                          className="font-semibold"
                          style={{ color: "var(--ocean)" }}
                        >
                          {row.clauseNo}
                        </div>
                        <Badge
                          className="mt-1 whitespace-nowrap border-transparent"
                          style={{
                            color: responseColor,
                            background:
                              decision.kind === "accept"
                                ? "var(--success-soft)"
                                : decision.kind === "reject"
                                  ? "var(--coral-soft)"
                                  : "var(--info-soft)",
                          }}
                        >
                          {response}
                        </Badge>
                      </TableCell>

                      <TableCell className="align-top text-xs leading-6">
                        {row.original}
                      </TableCell>

                      <TableCell className="align-top text-xs leading-6">
                        {row.requested}
                      </TableCell>

                      <TableCell
                        className="align-top text-xs leading-6"
                        style={{
                          color: responseColor,
                          fontWeight: 500,
                        }}
                      >
                        {responseText(
                          row.id,
                          row.original,
                          row.requested,
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPreviewOpen(false)}
            >
              {t("rvw.cmp.close")}
            </Button>

            <Button
              className="gap-1.5"
              style={{ background: "var(--navy)" }}
              disabled={submitting || !allDecided}
              onClick={() => void send()}
            >
              <Send className="size-4" />
              {t("rvw.send")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
