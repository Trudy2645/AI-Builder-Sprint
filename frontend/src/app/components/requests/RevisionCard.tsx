import { Trash2, Lightbulb, Sparkles } from "lucide-react";
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
import type { Contract } from "../../data/contracts";

export interface RevisionDraft {
  id: string;
  clauseNo: string;
  changeType: string;
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
  const clause = contract.clauses.find((c) => c.no === draft.clauseNo);
  const aiText = clause?.risk?.recommendation;

  const set = (patch: Partial<RevisionDraft>) => onChange({ ...draft, ...patch });

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
        {/* Clause select */}
        <div className="flex flex-col gap-1.5">
          <Label>{t("rev.selectClause")}</Label>
          <Select value={draft.clauseNo} onValueChange={(v) => set({ clauseNo: v })}>
            <SelectTrigger><SelectValue placeholder={t("rev.selectClausePlaceholder")} /></SelectTrigger>
            <SelectContent>
              {contract.clauses.map((c) => (
                <SelectItem key={c.no} value={c.no}>{c.no} · {c.title}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Original wording */}
        {clause && (
          <div className="flex flex-col gap-1.5">
            <Label>{t("rev.original")}</Label>
            <div className="rounded-md border border-border p-3 text-muted-foreground" style={{ background: "var(--muted)", fontSize: "13px", lineHeight: 1.6 }}>
              {clause.text}
            </div>
          </div>
        )}

        {/* Change type */}
        <div className="flex flex-col gap-1.5">
          <Label>{t("rev.changeType")}</Label>
          <Select value={draft.changeType} onValueChange={(v) => set({ changeType: v })}>
            <SelectTrigger><SelectValue placeholder={t("rev.changeType")} /></SelectTrigger>
            <SelectContent>
              <SelectItem value="edit">{t("opt.ct.edit")}</SelectItem>
              <SelectItem value="delete">{t("opt.ct.delete")}</SelectItem>
              <SelectItem value="add">{t("opt.ct.add")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* AI recommendation */}
        <div className="rounded-lg border p-3" style={{ borderColor: aiText ? "var(--teal)" : "var(--border)", background: aiText ? "var(--success-soft)" : "var(--muted)" }}>
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: aiText ? "var(--teal)" : "var(--muted-foreground)", fontSize: "12px", fontWeight: 600 }}>
              <Sparkles className="size-3.5" />
              {t("rev.aiRecommend")}
            </span>
            {aiText && (
              <Button type="button" variant="outline" size="sm" className="h-7 gap-1 whitespace-nowrap" style={{ borderColor: "var(--teal)", color: "var(--teal)" }} onClick={() => set({ requested: aiText })}>
                <Lightbulb className="size-3.5" />
                {t("rev.applyAi")}
              </Button>
            )}
          </div>
          <p className="mt-1.5 text-foreground" style={{ fontSize: "13px", lineHeight: 1.6 }}>
            {aiText ?? t("rev.noAi")}
          </p>
        </div>

        {/* Requested wording */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`req-${draft.id}`}>{t("rev.requested")}</Label>
          <Textarea id={`req-${draft.id}`} rows={3} value={draft.requested} onChange={(e) => set({ requested: e.target.value })} />
        </div>

        {/* Reason */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`reason-${draft.id}`}>{t("rev.reason")}</Label>
          <Textarea id={`reason-${draft.id}`} rows={2} value={draft.reason} onChange={(e) => set({ reason: e.target.value })} />
        </div>

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
