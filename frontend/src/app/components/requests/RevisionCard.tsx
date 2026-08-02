import { useEffect, useState } from "react";
import { Trash2, Lightbulb, LoaderCircle, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Button } from "../ui/button";
import { FileField } from "../auth/AuthFields";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { useApp } from "../../context/AppContext";
import { friendlyApiError, generateRevisionSuggestion } from "../../lib/api";
import type { Contract } from "../../lib/catalog";

export interface RevisionDraft {
  id: string;
  clauseNo: string;
  changeType: "edit" | "delete" | "add";
  requested: string;
  reason: string;
  attachment: string;
}

export function RevisionCard({
  index,
  contract,
  draft,
  onChange,
  onRemove,
}: {
  index: number;
  contract: Contract;
  draft: RevisionDraft;
  onChange: (d: RevisionDraft) => void;
  onRemove: () => void;
}) {
  const { t } = useApp();
  const clause = contract.clauses.find((candidate) => candidate.id === draft.clauseNo);
  const [aiText, setAiText] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  const set = (patch: Partial<RevisionDraft>) => onChange({ ...draft, ...patch });

  useEffect(() => {
    setAiText(null);
  }, [draft.changeType, draft.clauseNo, draft.reason]);

  const changeType = (value: RevisionDraft["changeType"]) => {
    set({
      changeType: value,
      clauseNo: value === "add" ? "" : draft.clauseNo || contract.clauses[0]?.id || "",
      requested: value === "delete" ? "" : draft.requested,
    });
  };

  const generateAi = async () => {
    if (!draft.reason.trim() || (draft.changeType === "edit" && !clause)) return;
    setAiLoading(true);
    try {
      const result = await generateRevisionSuggestion(draft.changeType === "add"
        ? { request_type: "add", reason: draft.reason.trim() }
        : {
            request_type: "modify",
            clause_id: clause!.id,
            clause_title: clause!.title,
            original_text: clause!.text,
            reason: draft.reason.trim(),
          });
      setAiText(result.suggestion);
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <span className="flex items-center gap-2 whitespace-nowrap" style={{ fontWeight: 600, color: "var(--navy)" }}>
          <span className="flex size-6 items-center justify-center rounded-full" style={{ background: "var(--ocean)", color: "#fff", fontSize: "12px" }}>
            {index + 1}
          </span>
          {t("rev.card")}
        </span>
        <Button variant="ghost" size="sm" className="gap-1 whitespace-nowrap" style={{ color: "var(--coral)" }} onClick={onRemove}>
          <Trash2 className="size-4" />
        </Button>
      </div>

      <div className="flex flex-col gap-4">
        {/* Change type */}
        <div className="flex flex-col gap-1.5">
          <Label>{t("rev.changeType")}</Label>
          <Select value={draft.changeType} onValueChange={(value) => changeType(value as RevisionDraft["changeType"])}>
            <SelectTrigger><SelectValue placeholder={t("rev.changeType")} /></SelectTrigger>
            <SelectContent>
              <SelectItem value="edit">{t("opt.ct.edit")}</SelectItem>
              <SelectItem value="delete">{t("opt.ct.delete")}</SelectItem>
              <SelectItem value="add">{t("opt.ct.add")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Clause select */}
        {draft.changeType !== "add" && <div className="flex flex-col gap-1.5">
          <Label>{t("rev.selectClause")}</Label>
          <Select value={draft.clauseNo} onValueChange={(value) => set({ clauseNo: value })}>
            <SelectTrigger><SelectValue placeholder={t("rev.selectClausePlaceholder")} /></SelectTrigger>
            <SelectContent>
              {contract.clauses.map((item) => (
                <SelectItem key={item.id} value={item.id}>제{item.no}조 · {item.title}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>}

        {/* Original wording */}
        {draft.changeType !== "add" && clause && (
          <div className="flex flex-col gap-1.5">
            <Label>{t("rev.original")}</Label>
            <div className="rounded-md border border-border p-3 text-muted-foreground" style={{ background: "var(--muted)", fontSize: "13px", lineHeight: 1.6 }}>
              {clause.text}
            </div>
          </div>
        )}

        {/* Reason */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`reason-${draft.id}`}>{t("rev.reason")}</Label>
          <Textarea id={`reason-${draft.id}`} rows={2} value={draft.reason} onChange={(event) => set({ reason: event.target.value })} />
        </div>

        {/* AI recommendation */}
        {draft.changeType !== "delete" && <div className="rounded-lg border p-3" style={{ borderColor: aiText ? "var(--teal)" : "var(--border)", background: aiText ? "var(--success-soft)" : "var(--muted)" }}>
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: aiText ? "var(--teal)" : "var(--muted-foreground)", fontSize: "12px", fontWeight: 600 }}>
              <Sparkles className="size-3.5" />
              {t("rev.aiRecommend")}
            </span>
            <div className="flex gap-1.5">
              <Button type="button" variant="outline" size="sm" className="h-7 gap-1 whitespace-nowrap" disabled={aiLoading || !draft.reason.trim() || (draft.changeType === "edit" && !clause)} onClick={() => void generateAi()}>
                {aiLoading ? <LoaderCircle className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
                {t("rev.generateAi")}
              </Button>
              {aiText && (
              <Button type="button" variant="outline" size="sm" className="h-7 gap-1 whitespace-nowrap" style={{ borderColor: "var(--teal)", color: "var(--teal)" }} onClick={() => set({ requested: aiText })}>
                <Lightbulb className="size-3.5" />
                {t("rev.applyAi")}
              </Button>
              )}
            </div>
          </div>
          <p className="mt-1.5 text-foreground" style={{ fontSize: "13px", lineHeight: 1.6 }}>
            {aiLoading ? t("rev.aiLoading") : aiText ?? (draft.reason.trim() ? t("rev.noAi") : t("rev.aiReasonFirst"))}
          </p>
        </div>}

        {/* Requested wording */}
        {draft.changeType !== "delete" && <div className="flex flex-col gap-1.5">
          <Label htmlFor={`req-${draft.id}`}>{t("rev.requested")}</Label>
          <Textarea id={`req-${draft.id}`} rows={3} value={draft.requested} onChange={(e) => set({ requested: e.target.value })} />
        </div>}

        {/* Attachment */}
        <FileField
          id={`file-${draft.id}`}
          label={t("rev.attachment")}
          fileName={draft.attachment}
          onChange={(name) => set({ attachment: name })}
        />
      </div>
    </div>
  );
}
