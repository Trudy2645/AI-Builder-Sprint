import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { useApp } from "../../context/AppContext";
import { CATEGORIES, DISTRICTS } from "../../lib/catalog";
import type { ListingDraft } from "../../store/ListingsContext";

type Patch = Partial<ListingDraft>;

type FieldProps = { label: string; required?: boolean; error?: string; children: React.ReactNode };

function Field({ label, required = false, error, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="whitespace-nowrap">{label}{required && <span className="ml-1 text-destructive">*</span>}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

const PRICE_UNITS = ["객실당", "1인당", "1동당", "1좌석당", "1팀당"];

type FieldErrors = Partial<Record<keyof ListingDraft, string>>;

export function ProductFields({ draft, onChange, errors = {} }: { draft: ListingDraft; onChange: (p: Patch) => void; errors?: FieldErrors }) {
  const { t } = useApp();
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Field label={t("lf.productName")} required error={errors.productName}>
          <Input aria-invalid={!!errors.productName} className={errors.productName ? "border-destructive" : ""} value={draft.productName} placeholder={t("lf.productNamePh")} onChange={(e) => onChange({ productName: e.target.value })} />
        </Field>
      </div>
      <Field label={t("lf.category")} required error={errors.category}>
        <Select value={draft.category || undefined} onValueChange={(v) => onChange({ category: v as ListingDraft["category"] })}>
          <SelectTrigger className={errors.category ? "border-destructive" : ""}><SelectValue placeholder={t("filter.category")} /></SelectTrigger>
          <SelectContent>
            {CATEGORIES.filter((c) => c.value !== "all").map((c) => (
              <SelectItem key={c.value} value={c.value}>{t(c.labelKey)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label={t("lf.district")} required error={errors.district}>
        <Select value={draft.district || undefined} onValueChange={(v) => onChange({ district: v })}>
          <SelectTrigger className={errors.district ? "border-destructive" : ""}><SelectValue placeholder={t("filter.district")} /></SelectTrigger>
          <SelectContent>
            {DISTRICTS.map((d) => (
              <SelectItem key={d} value={d}>{d}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
    </div>
  );
}

export function SupplyFields({ draft, onChange, errors = {} }: { draft: ListingDraft; onChange: (p: Patch) => void; errors?: FieldErrors }) {
  const { t } = useApp();
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Field label="공고 가능 시작일" required error={errors.availabilityStart}>
        <Input aria-invalid={!!errors.availabilityStart} className={errors.availabilityStart ? "border-destructive" : ""} type="date" value={draft.availabilityStart} onChange={(e) => onChange({ availabilityStart: e.target.value })} />
      </Field>
      <Field label="공고 가능 종료일" required error={errors.availabilityEnd}>
        <Input aria-invalid={!!errors.availabilityEnd} className={errors.availabilityEnd ? "border-destructive" : ""} type="date" value={draft.availabilityEnd} onChange={(e) => onChange({ availabilityEnd: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Field label={t("lf.quantity")} required error={errors.quantity}>
          <Input aria-invalid={!!errors.quantity} className={errors.quantity ? "border-destructive" : ""} value={draft.quantity} placeholder={t("lf.quantityPh")} onChange={(e) => onChange({ quantity: e.target.value })} />
        </Field>
      </div>
      <Field label={t("lf.unitPrice")} required error={errors.unitPrice}>
        <Input aria-invalid={!!errors.unitPrice} className={errors.unitPrice ? "border-destructive" : ""} type="number" min={1} value={draft.unitPrice} onChange={(e) => onChange({ unitPrice: e.target.value })} />
      </Field>
      <Field label={t("lf.priceUnit")} required error={errors.priceUnit}>
        <Select value={draft.priceUnit} onValueChange={(v) => onChange({ priceUnit: v })}>
          <SelectTrigger className={errors.priceUnit ? "border-destructive" : ""}><SelectValue /></SelectTrigger>
          <SelectContent>
            {PRICE_UNITS.map((u) => (
              <SelectItem key={u} value={u}>{u}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label={t("lf.minQty")}>
        <Input type="number" min={0} value={draft.minQty} onChange={(e) => onChange({ minQty: e.target.value })} />
      </Field>
      <Field label={t("lf.maxQty")}>
        <Input type="number" min={0} value={draft.maxQty} onChange={(e) => onChange({ maxQty: e.target.value })} />
      </Field>
    </div>
  );
}

export function TermsFields({ draft, onChange, errors = {} }: { draft: ListingDraft; onChange: (p: Patch) => void; errors?: FieldErrors }) {
  const { t } = useApp();
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Field label={t("lf.cancellation")} required error={errors.cancellation}>
        <Textarea aria-invalid={!!errors.cancellation} className={errors.cancellation ? "border-destructive" : ""} rows={4} value={draft.cancellation} placeholder={t("lf.cancellationPh")} onChange={(e) => onChange({ cancellation: e.target.value })} />
      </Field>
      <Field label={t("lf.noShow")} required error={errors.noShow}>
        <Textarea aria-invalid={!!errors.noShow} className={errors.noShow ? "border-destructive" : ""} rows={4} value={draft.noShow} placeholder={t("lf.noShowPh")} onChange={(e) => onChange({ noShow: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Field label={t("lf.settlement")} required error={errors.settlement}>
          <Textarea aria-invalid={!!errors.settlement} className={errors.settlement ? "border-destructive" : ""} rows={3} value={draft.settlement} placeholder={t("lf.settlementPh")} onChange={(e) => onChange({ settlement: e.target.value })} />
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Field label={t("lf.liability")} required error={errors.liability}>
          <Textarea aria-invalid={!!errors.liability} className={errors.liability ? "border-destructive" : ""} rows={2} value={draft.liability} placeholder={t("lf.liabilityPh")} onChange={(e) => onChange({ liability: e.target.value })} />
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Field label={t("lf.termination")} required error={errors.termination}>
          <Input aria-invalid={!!errors.termination} className={errors.termination ? "border-destructive" : ""} value={draft.termination} placeholder={t("lf.terminationPh")} onChange={(e) => onChange({ termination: e.target.value })} />
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Field label={t("lf.special")}>
          <Textarea rows={2} value={draft.special} placeholder={t("lf.specialPh")} onChange={(e) => onChange({ special: e.target.value })} />
        </Field>
      </div>
    </div>
  );
}
