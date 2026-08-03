import { useEffect, useMemo, useRef, useState, type DragEvent, type PointerEvent } from "react";
import { ArrowLeft, CalendarDays, CheckSquare, LoaderCircle, MousePointer2, PenLine, Type } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?worker";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { dispatchSignatureRequest, getSignatureSourcePdf } from "../../lib/api";

// Let Vite bundle and instantiate the PDF.js worker directly. Using a URL here
// can make the dev server fall back to a module worker URL that fails to load.
GlobalWorkerOptions.workerPort = new PdfWorker();

type FieldType = "SIGNATURE" | "TEXT" | "SIGNING_DATE" | "DATE" | "CHECKBOX";
type Field = { id: string; type: FieldType; page: number; x: number; y: number; width: number; height: number; fontSize: number; required: boolean; textAlign: "LEFT" | "CENTER" | "RIGHT"; dataLabel: string };
const palette: Array<{ type: FieldType; label: string; icon: typeof PenLine }> = [{ type: "SIGNATURE", label: "서명", icon: PenLine }, { type: "TEXT", label: "텍스트", icon: Type }, { type: "SIGNING_DATE", label: "서명한 날짜", icon: CalendarDays }, { type: "DATE", label: "날짜", icon: CalendarDays }, { type: "CHECKBOX", label: "체크", icon: CheckSquare }];
const sizeFor = (_type: FieldType) => ({ width: 10, height: 2 });
const clamp = (value: number, size: number) => Math.max(0, Math.min(100 - size, value));

function PdfPage({ pdf, page, fields, onDrop, onMove, onStart, selectedId }: { pdf: ArrayBuffer; page: number; fields: Field[]; onDrop: (event: DragEvent<HTMLDivElement>, page: number) => void; onMove: (event: PointerEvent<HTMLDivElement>, page: number) => void; onStart: (event: PointerEvent<HTMLDivElement>, id: string) => void; selectedId: string | null }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const render = async () => {
      setFailed(false);
      try {
        // PDF.js applies each page's CropBox and /Rotate. The overlay is a percentage
        // of this rendered surface, so CSS scaling cannot change the saved coordinate.
        const document = await getDocument({
          data: new Uint8Array(pdf.slice(0)),
          // Avoid a Vite dev-server dependency on PDF.js v5's wasm assets.
          useWasm: false,
        }).promise;
        const pdfPage = await document.getPage(page); // PDF.js page API is 1-based.
        const viewport = pdfPage.getViewport({ scale: 2 });
        const target = canvas.current;
        if (!target || cancelled) return;
        target.width = Math.ceil(viewport.width);
        target.height = Math.ceil(viewport.height);
        const context = target.getContext("2d");
        if (!context) return;
        await pdfPage.render({ canvasContext: context, viewport }).promise;
        document.destroy();
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    void render();
    return () => { cancelled = true; };
  }, [page, pdf]);
  return <div className="mb-6"><p className="mb-2 text-center text-xs text-muted-foreground">페이지 {page}</p><div onDragOver={(event) => event.preventDefault()} onDrop={(event) => onDrop(event, page)} onPointerMove={(event) => onMove(event, page)} className="relative mx-auto w-fit max-w-full overflow-hidden bg-white shadow-lg"><canvas ref={canvas} className="block max-w-full" />{failed && <p className="absolute inset-0 grid place-items-center bg-white text-sm text-destructive">PDF 페이지를 렌더링하지 못했습니다.</p>}{fields.map((field) => { const item = palette.find((entry) => entry.type === field.type)!; const Icon = item.icon; return <div key={field.id} onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); onStart(event, field.id); }} className={`absolute flex cursor-grab touch-none select-none items-center justify-center overflow-hidden border-2 border-dashed bg-sky-100/90 px-0.5 leading-none text-[10px] text-[var(--ocean)] ${selectedId === field.id ? "border-[var(--navy)] ring-2 ring-[var(--ocean)]/30" : "border-[var(--ocean)]"}`} style={{ left: `${field.x}%`, top: `${field.y}%`, width: `${field.width}%`, height: `${field.height}%` }}><Icon className="mr-0.5 size-3 shrink-0" /><span className="min-w-0 truncate whitespace-nowrap font-bold">{item.label}</span></div>; })}</div></div>;
}

export function SignatureFieldPlacementPage() {
  const navigate = useNavigate(); const [params] = useSearchParams(); const contractId = params.get("contractId"); const versionId = params.get("versionId");
  const [fields, setFields] = useState<Field[]>([]); const [selectedId, setSelectedId] = useState<string | null>(null); const [dragging, setDragging] = useState<{ id: string; pointerId: number } | null>(null); const [sending, setSending] = useState(false); const [pdf, setPdf] = useState<ArrayBuffer | null>(null); const [pageCount, setPageCount] = useState(0); const [pdfHash, setPdfHash] = useState(""); const [previewError, setPreviewError] = useState<string | null>(null);
  useEffect(() => { if (!contractId || !versionId) { setPreviewError("계약 ID와 버전 ID가 필요합니다."); return; } setPreviewError(null); void getSignatureSourcePdf(contractId, versionId).then(async ({ bytes, pageCount: headerPageCount, sha256 }) => { const document = await getDocument({ data: new Uint8Array(bytes.slice(0)), useWasm: false }).promise; const count = headerPageCount || document.numPages; document.destroy(); if (count < 1) throw new Error("계약서에 페이지가 없습니다."); setPdf(bytes); setPageCount(count); setPdfHash(sha256); }).catch((error) => { const message = error instanceof Error ? error.message : "계약서 PDF를 불러오지 못했습니다."; setPreviewError(message); toast.error(message); }); }, [contractId, versionId]);
  const addAt = (event: DragEvent<HTMLDivElement>, page: number) => { const type = event.dataTransfer.getData("application/x-busanlink-field") as FieldType; if (!palette.some((item) => item.type === type)) return; const rect = event.currentTarget.getBoundingClientRect(); const size = sizeFor(type); const x = clamp(((event.clientX - rect.left) / rect.width) * 100, size.width); const y = clamp(((event.clientY - rect.top) / rect.height) * 100, size.height); const id = crypto.randomUUID(); setFields((all) => [...all, { id, type, page, x, y, fontSize: 12, required: true, textAlign: "LEFT", dataLabel: id.slice(0, 8), ...size }]); setSelectedId(id); };
  const moveAt = (event: PointerEvent<HTMLDivElement>, page: number) => { if (!dragging || dragging.pointerId !== event.pointerId) return; const rect = event.currentTarget.getBoundingClientRect(); const field = fields.find((item) => item.id === dragging.id); if (!field) return; const x = clamp(((event.clientX - rect.left) / rect.width) * 100 - field.width / 2, field.width); const y = clamp(((event.clientY - rect.top) / rect.height) * 100 - field.height / 2, field.height); setFields((all) => all.map((item) => item.id === field.id ? { ...item, page, x, y } : item)); };
  const selected = fields.find((field) => field.id === selectedId); const update = (patch: Partial<Field>) => setFields((all) => all.map((field) => { if (field.id !== selectedId) return field; const next = { ...field, ...patch }; return { ...next, x: clamp(next.x, next.width), y: clamp(next.y, next.height) }; }));
  const payload = useMemo(() => fields.map((field) => ({ field_type: field.type, data_label: field.dataLabel, required: field.required, font_size: field.fontSize, text_align: field.textAlign, position: { page: field.page, x: Number((field.x / 100).toFixed(4)), y: Number((field.y / 100).toFixed(4)) }, size: { width: Number((field.width / 100).toFixed(4)), height: Number((field.height / 100).toFixed(4)) } })), [fields]);
  const send = async () => { if (!contractId || !versionId || !pdf) { toast.error("계약서 PDF를 먼저 불러와 주세요."); return; } setSending(true); try { await dispatchSignatureRequest(contractId, versionId, payload); toast.success("미리보기와 동일한 계약 PDF를 모두싸인으로 발송했습니다."); } catch (error) { toast.error(error instanceof Error ? error.message : "발송에 실패했습니다."); } finally { setSending(false); } };
  return <div className="mx-auto max-w-[1320px]"><Button variant="ghost" className="mb-4" onClick={() => navigate(-1)}><ArrowLeft className="mr-1 size-4" />최종 승인으로</Button><PageHeader title="서명·입력란 배치" description="현재 계약 버전의 실제 PDF 위에 입력란을 배치합니다." />{pdfHash && <p className="mb-3 text-xs text-muted-foreground">발송 원본 SHA-256: {pdfHash.slice(0, 12)}… · {pageCount}페이지</p>}<div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)_300px]"><aside className="h-fit rounded-xl border border-border bg-card p-4"><h2 className="font-semibold">입력란 도구</h2><div className="mt-3 space-y-2">{palette.map((item) => { const Icon = item.icon; return <div key={item.type} draggable onDragStart={(event) => event.dataTransfer.setData("application/x-busanlink-field", item.type)} className="flex cursor-grab items-center gap-2 rounded-lg border p-3 text-sm"><Icon className="size-4" />{item.label}</div>; })}</div><p className="mt-4 text-xs text-muted-foreground"><MousePointer2 className="mr-1 inline size-3" />PDF 안으로 끌어 놓으세요.</p></aside><main onPointerUp={() => setDragging(null)} className="h-[76vh] overflow-y-auto rounded-xl border bg-muted/40 p-4 sm:p-8">{pdf ? Array.from({ length: pageCount }, (_, index) => <PdfPage key={index + 1} pdf={pdf} page={index + 1} fields={fields.filter((field) => field.page === index + 1)} onDrop={addAt} onMove={moveAt} onStart={(event, id) => { setSelectedId(id); setDragging({ id, pointerId: event.pointerId }); }} selectedId={selectedId} />) : previewError ? <div className="grid h-full place-items-center text-center text-sm"><div><p className="font-medium text-destructive">계약서 PDF를 불러오지 못했습니다.</p><p className="mt-2 text-muted-foreground">{previewError}</p><Button className="mt-4" variant="outline" onClick={() => window.location.reload()}>다시 시도</Button></div></div> : <div className="grid h-full place-items-center text-sm text-muted-foreground"><LoaderCircle className="mr-2 size-4 animate-spin" />계약서 PDF를 불러오는 중입니다.</div>}</main><aside className="h-fit rounded-xl border border-border bg-card p-4"><h2 className="font-semibold">필드 속성</h2>{selected ? <div className="mt-3 space-y-3 text-xs"><p className="font-semibold">{palette.find((item) => item.type === selected.type)?.label}</p><label className="block">너비 {selected.width}%<input className="mt-1 w-full" type="range" min="3" max="35" step="0.5" value={selected.width} onChange={(event) => update({ width: Number(event.target.value) })} /></label><label className="block">높이 {selected.height}%<input className="mt-1 w-full" type="range" min="2" max="15" step="0.5" value={selected.height} onChange={(event) => update({ height: Number(event.target.value) })} /></label><label className="flex justify-between">필수 입력<input type="checkbox" checked={selected.required} onChange={(event) => update({ required: event.target.checked })} /></label><label className="block">데이터 라벨<input className="mt-1 w-full rounded border p-1" value={selected.dataLabel} onChange={(event) => update({ dataLabel: event.target.value })} /></label><Button variant="outline" className="w-full" onClick={() => setFields((all) => all.filter((field) => field.id !== selected.id))}>삭제</Button></div> : <p className="mt-3 text-sm text-muted-foreground">필드를 선택해 주세요.</p>}<Button className="mt-6 w-full" disabled={sending || !pdf} onClick={() => void send()}>{sending ? <><LoaderCircle className="mr-2 size-4 animate-spin" />모두싸인 발송 중...</> : <><PenLine className="mr-1 size-4" />모두싸인 발송</>}</Button>{sending && <div className="mt-3 rounded-lg bg-muted p-3 text-center text-xs text-muted-foreground"><div className="mx-auto mb-2 h-1.5 w-full overflow-hidden rounded-full bg-border"><div className="h-full w-1/2 animate-pulse rounded-full bg-[var(--ocean)]" /></div>PDF 업로드 및 모두싸인 문서를 만드는 중입니다. 잠시만 기다려 주세요.</div>}</aside></div></div>;
}
