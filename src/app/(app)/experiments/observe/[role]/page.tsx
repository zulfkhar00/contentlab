"use client";

import { useEffect, useState } from "react";
import { videoApi } from "@/lib/api-client";
import { useUpsertObservation } from "@/lib/query-hooks";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  useExperiment,
  getVariant,
  emptyObservation,
  type VariantObservation,
  type VariantRole,
} from "@/lib/experiment";

function MonoLabel({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">{children}</span>;
}

function DeliveredToggle({ value, onChange }: { value: boolean | null; onChange: (v: boolean) => void; }) {
  return (
    <div className="flex items-center gap-2" data-testid="delivered-toggle">
      {([true, false] as const).map((v) => (
        <button key={String(v)} type="button" data-delivered-choice={String(v)} onClick={() => onChange(v)}
          className={"rounded border px-3 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors " + (value === v ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-muted-foreground")}
        >{v ? "Yes" : "No"}</button>
      ))}
    </div>
  );
}

export default function ObservePage() {
  const params = useParams();
  const role = (typeof params?.role === "string" ? params.role : "").toUpperCase() as VariantRole;
  const { experiment, loaded } = useExperiment();
  const upsertObservation = useUpsertObservation();
  if (!experiment) return (
    <div className="border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground">
      No active experiment.
    </div>
  );
  const variant = loaded ? getVariant(experiment, role) : null;
  const [obs, setObs] = useState<VariantObservation>(emptyObservation);

  useEffect(() => {
    if (variant?.observation) setObs({ ...emptyObservation(), ...variant.observation });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  function patch(update: Partial<VariantObservation>) {
    setObs((prev) => ({ ...prev, ...update }));
    const variantId = (variant as { id?: string })?.id;
    if (variantId) {
      upsertObservation.mutate({ id: variantId, data: update as Record<string, unknown> });
    }
  }

  if (!loaded) return null;

  if (!variant || !variant.tiktokUrl) {
    return (
      <div className="flex flex-col gap-4">
        <Button asChild variant="ghost" size="sm" className="w-fit gap-1">
          <Link href="/experiments"><ArrowLeft className="size-3.5" /> Back to Workspace</Link>
        </Button>
        <div className="border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground">
          {!variant ? "Unknown variant." : "This variant has no published URL yet."}
        </div>
      </div>
    );
  }

  const embedUrl = variant.tiktokUrl.replace(/^https:\/\/(www\.)?tiktok\.com/, "https://www.tiktok.com");

  return (
    <div className="flex flex-col gap-6" data-testid="observe-page">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm" className="gap-1">
            <Link href="/experiments"><ArrowLeft className="size-3.5" /> Workspace</Link>
          </Button>
          <span className="text-muted-foreground">/</span>
          <div className="flex items-center gap-2">
            <span className="inline-flex size-7 items-center justify-center bg-primary font-mono text-xs text-primary-foreground">{variant.role}</span>
            <h2 className="text-lg font-semibold tracking-tight">{variant.title}</h2>
          </div>
        </div>
        <div className="flex items-center gap-2"><Eye className="size-4 text-muted-foreground" /><MonoLabel>Observation</MonoLabel></div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <MonoLabel>Published Video</MonoLabel>
          <div className="relative w-full overflow-hidden border border-border bg-secondary" style={{ aspectRatio: "9/16", maxHeight: 640 }} data-testid="video-embed-zone">
            <iframe src={embedUrl} className="absolute inset-0 h-full w-full" allowFullScreen allow="autoplay" title={`Variant ${variant.role}`} />
            <div className="absolute inset-0 flex items-center justify-center bg-secondary text-center text-xs text-muted-foreground" style={{ zIndex: -1 }}>
              <span>Video blocked by browser.<br />Use the link below to open in TikTok.</span>
            </div>
          </div>
          <a href={variant.tiktokUrl} target="_blank" rel="noopener noreferrer" className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground underline">Open in TikTok</a>
        </div>

        <div className="flex flex-col gap-6">
          <section className="flex flex-col gap-3 border border-border bg-card p-4" data-testid="observation-delivered">
            <div className="flex flex-col gap-1">
              <MonoLabel>Delivered the variable?</MonoLabel>
              <p className="text-xs text-muted-foreground">Did this variant deliver{" "}<span className="font-medium text-foreground">{variant.variableUnderTest}</span>{" as intended?"}</p>
            </div>
            <DeliveredToggle value={obs.deliveredVariable} onChange={(v) => patch({ deliveredVariable: v })} />
            <div className="flex flex-col gap-1">
              <MonoLabel>Reason</MonoLabel>
              <Textarea data-testid="obs-reason" placeholder="What made it land or miss?" value={obs.reason} onChange={(e) => patch({ reason: e.target.value })} rows={2} className="resize-none text-sm" />
            </div>
          </section>

          <section className="flex flex-col gap-3 border border-border bg-card p-4" data-testid="observation-notes">
            <MonoLabel>Observations</MonoLabel>
            <Textarea data-testid="obs-notes" placeholder="What did you notice watching this video?" value={obs.notes} onChange={(e) => patch({ notes: e.target.value })} rows={4} className="resize-none text-sm" />
          </section>

          <section className="flex flex-col gap-4 border border-border bg-card p-4" data-testid="observation-signals">
            <MonoLabel>Signal Fields</MonoLabel>
            <div className="flex flex-col gap-1">
              <MonoLabel>Drop-off timecode</MonoLabel>
              <input data-testid="obs-dropoff" type="text" placeholder="e.g. 0:14" value={obs.dropOffAt} onChange={(e) => patch({ dropOffAt: e.target.value })} className="w-full border border-border bg-background px-3 py-1.5 font-mono text-sm outline-none focus:border-primary" />
            </div>
            <div className="flex flex-col gap-1">
              <MonoLabel>Comment sentiment</MonoLabel>
              <input data-testid="obs-sentiment" type="text" placeholder="e.g. Skeptical but curious" value={obs.sentiment} onChange={(e) => patch({ sentiment: e.target.value })} className="w-full border border-border bg-background px-3 py-1.5 font-mono text-sm outline-none focus:border-primary" />
            </div>
            <div className="flex flex-col gap-1">
              <MonoLabel>Unexpected signals</MonoLabel>
              <Textarea data-testid="obs-unexpected" placeholder="Anything surprising." value={obs.unexpected} onChange={(e) => patch({ unexpected: e.target.value })} rows={2} className="resize-none text-sm" />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
