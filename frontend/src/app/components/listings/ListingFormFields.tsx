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
import { CATEGORIES, DISTRICTS } from "../../data/contracts";
import type { ListingDraft } from "../../store/ListingsContext";

type Patch = Partial<ListingDraft>;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="whitespace-nowrap">{label}</Label>
      {children}
    </div>
  );
}

const PRICE_UNITS = ["객실당", "1인당", "1동당", "1좌석당", "1팀당"];

export function ProductFields({ draft, onChange }: { draft: ListingDraft; onChange: (p: Patch) => void }) {
  const { t } = useApp();
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Field label={t("lf.productName")}>
          <Input value={draft.productName} placeholder={t("lf.productNamePh")} onChange={(e) => onChange({ productName: e.target.value })} />
        </Field>
      </div>
      <Field label={t("lf.category")}>
        <Select value={draft.category || undefined} onValueChange={(v) => onChange({ category: v as ListingDraft["category"] })}>
          <SelectTrigger><SelectValue placeholder={t("filter.category")} /></SelectTrigger>
          <SelectContent>
            {CATEGORIES.filter((c) => c.value !== "all").map((c) => (
              <SelectItem key={c.value} value={c.value}>{t(c.labelKey)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label={t("lf.district")}>
        <Select value={draft.district || undefined} onValueChange={(v) => onChange({ district: v })}>
          <SelectTrigger><SelectValue placeholder={t("filter.district")} /></SelectTrigger>
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

export function SupplyFields({ draft, onChange }: { draft: ListingDraft; onChange: (p: Patch) => void }) {
  const { t } = useApp();
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Field label="공고 가능 시작일">
        <Input type="date" value={draft.availabilityStart} onChange={(e) => onChange({ availabilityStart: e.target.value })} />
      </Field>
      <Field label="공고 가능 종료일">
        <Input type="date" value={draft.availabilityEnd} onChange={(e) => onChange({ availabilityEnd: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Field label={t("lf.quantity")}>
          <Input value={draft.quantity} placeholder={t("lf.quantityPh")} onChange={(e) => onChange({ quantity: e.target.value })} />
        </Field>
      </div>
      <Field label={t("lf.unitPrice")}>
        <Input type="number" min={0} value={draft.unitPrice} onChange={(e) => onChange({ unitPrice: e.target.value })} />
      </Field>
      <Field label={t("lf.priceUnit")}>
        <Select value={draft.priceUnit} onValueChange={(v) => onChange({ priceUnit: v })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
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

export function TermsFields({ draft, onChange }: { draft: ListingDraft; onChange: (p: Patch) => void }) {
  const { t } = useApp();
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Field label={t("lf.cancellation")}>
        <Textarea rows={4} value={draft.cancellation} placeholder={t("lf.cancellationPh")} onChange={(e) => onChange({ cancellation: e.target.value })} />
      </Field>
      <Field label={t("lf.noShow")}>
        <Textarea rows={4} value={draft.noShow} placeholder={t("lf.noShowPh")} onChange={(e) => onChange({ noShow: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Field label={t("lf.settlement")}>
          <Textarea rows={3} value={draft.settlement} placeholder={t("lf.settlementPh")} onChange={(e) => onChange({ settlement: e.target.value })} />
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Field label={t("lf.liability")}>
          <Textarea rows={2} value={draft.liability} placeholder={t("lf.liabilityPh")} onChange={(e) => onChange({ liability: e.target.value })} />
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Field label={t("lf.termination")}>
          <Input value={draft.termination} placeholder={t("lf.terminationPh")} onChange={(e) => onChange({ termination: e.target.value })} />
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
