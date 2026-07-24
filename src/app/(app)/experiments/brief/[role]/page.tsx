"use client";

// Screen 5 (Variant Review + Recording Brief) per actionable_ui_ux_changes.md
// section 7. Answers: "Can the founder execute this variant while preserving
// the experiment design?".

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Camera,
  Check,
  ClipboardCheck,
  Copy,
  FileText,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { variantApi, videoApi } from "@/lib/api-client";
import {
  useExperiment,
  getVariant,
  getNextActionVariant,
  variantStatusLabel,
  isValidTiktokUrl,
  type Variant,
  type VariantRole,
  type VariantBriefEdit,
} from "@/lib/experiment";
import { useProjectContext } from "@/lib/project-context";

type ScriptTag = "VARIABLE" | "CONTROLLED";
const SCRIPT_ROWS: Array<{ time: string; segment: string; tag: ScriptTag }> = [
  { time: "0–5s",  segment: "Hook",    tag: "VARIABLE" },
  { time: "5–15s", segment: "Context", tag: "VARIABLE" },
  { time: "15–30s", segment: "Lesson", tag: "CONTROLLED" },
  { time: "30–42s", segment: "Product", tag: "CONTROLLED" },
  { time: "42–48s", segment: "CTA",    tag: "CONTROLLED" },
];

const RECORDING_GUIDE: Array<{ label: string; value: string }> = [
  { label: "Camera",          value: "Eye level, medium close-up" },
  { label: "Delivery",        value: "Calm, direct, slightly reflective" },
  { label: "Background",      value: "Use the same environment as other variants" },
  { label: "Duration Target", value: "45–50 seconds" },
];

const QUICK_ACTIONS = ["Make it punchier", "Shorten", "More vulnerable", "More casual"];

function craftBriefRevision(v: Variant, instruction: string): VariantBriefEdit {
  const trimmed = instruction.trim();
  const framing = trimmed || "a sharper hook";
  const base = v.hook.replace(/\.$/, "");
  return {
    hook: base + ", reframed around " + framing + ".",
    hookDeliveryNote: trimmed ? "Deliver with " + framing + "." : v.hookDeliveryNote,
    context: v.context,
    onScreenText: v.onScreenText,
  };
}

function TagPill({ tag }: { tag: ScriptTag }) {
  return (
    <span
      className={"rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide " + (
        tag === "VARIABLE"
          ? "bg-primary text-primary-foreground"
          : "border border-border bg-secondary text-muted-foreground"
      )}
    >
      {tag}
    </span>
  );
}

function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

type ApprovalStage = "pending" | "approved" | "recorded" | "published";

export default function RecordingBriefPage() {
  const params = useParams<{ role: string }>();
  const { experiment, startTracking, updateVariantBrief } = useExperiment();
  const { context: projectContext } = useProjectContext();
  const variant = getVariant(experiment, params.role);
  const nextVariant = getNextActionVariant(experiment.variants);

  const [urlDraft, setUrlDraft] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const [revision, setRevision] = useState<VariantBriefEdit | null>(null);
  const [stage, setStage] = useState<ApprovalStage>("pending");
  const [factState, setFactState] = useState<"unknown" | "confirmed" | "flagged">("unknown");
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [pubChecks, setPubChecks] = useState({ videoLive: false, variableDelivered: false, controlledPreserved: false });

  if (!variant) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          No variant found for &quot;{params.role}&quot;.
        </p>
        <Button asChild variant="outline" className="w-fit gap-2">
          <Link href="/experiments">
            <ArrowLeft className="size-4" />
            Back to Experiment
          </Link>
        </Button>
      </div>
    );
  }

  const isNext = variant.role === nextVariant?.role;
  const isLive = variant.status === "tracking" || variant.status === "completed";

  const scriptContent: Record<string, { text: string; note?: string }> = {
    Hook:    { text: variant.hook, note: variant.hookDeliveryNote },
    Context: { text: variant.context },
    Lesson:  { text: experiment.script.lesson },
    Product: { text: experiment.script.product },
    CTA:     { text: experiment.script.cta },
  };

  function copy(label: string, text: string) {
    navigator.clipboard?.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  }

  function copyScript() {
    const text = SCRIPT_ROWS.map((r) => {
      const body = scriptContent[r.segment].text;
      return r.segment + " (" + r.time + ") [" + r.tag + "]: \"" + body + "\"";
    }).join("\n");
    copy("script", text);
  }

  function submitUrl(role: VariantRole) {
    const trimmed = urlDraft.trim();
    if (!isValidTiktokUrl(trimmed)) {
      setUrlError("Paste a valid TikTok video URL (https://tiktok.com/...).".replace("XX","XX"));
      return;
    }
    setUrlError(null);
    setPubChecks({ videoLive: false, variableDelivered: false, controlledPreserved: false });
    setShowPublishModal(true);
  }

  function confirmPublish(role: VariantRole) {
    const vid = experiment.variants.find(v => v.role === role);
    if (vid) {
      variantApi.createVideo((vid as {id?: string}).id ?? "")
        .then(video => videoApi.submitUrl(video.id, urlDraft.trim(), {
          video_live: pubChecks.videoLive,
          variable_delivered: pubChecks.variableDelivered,
          controlled_preserved: pubChecks.controlledPreserved,
        }))
        .catch(() => {});
    }
    startTracking(role, urlDraft.trim());
    setUrlDraft("");
    setShowPublishModal(false);
    setStage("published");
  }

  function rewriteBrief() {
    setRevision(craftBriefRevision(variant!, instruction));
  }
  function applyRevision() {
    if (!revision) return;
    updateVariantBrief(variant!.role, revision);
    setRevision(null);
    setInstruction("");
  }
  function discardRevision() { setRevision(null); }

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
          <Link href="/experiments" className="flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="size-3.5" />
            Back to Experiment
          </Link>
          <span className="text-border">/</span>
          <span>Variant {variant.role}</span>
        </div>
        <span className="rounded border border-border bg-card px-2.5 py-1 font-mono text-xs uppercase tracking-wide text-muted-foreground">
          {variantStatusLabel(variant.status)}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <MonoLabel>Experiment: {experiment.name}</MonoLabel>
        <span className="w-fit rounded border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
          {variant.roleLabel}
        </span>
        <h2 className="text-2xl font-semibold tracking-tight">
          Variant {variant.role} — {variant.title}
        </h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Can you execute this variant while preserving the experiment design?
        </p>
      </div>

      <section data-testid="experiment-context" className="grid grid-cols-1 gap-3 border border-border bg-card p-5 md:grid-cols-3">
        <div className="flex flex-col gap-1">
          <MonoLabel>Variable Under Test</MonoLabel>
          <span className="text-sm">Opening framing</span>
        </div>
        <div className="flex flex-col gap-1">
          <MonoLabel>This Variant Changes</MonoLabel>
          <span className="text-sm">{variant.variableUnderTest}</span>
        </div>
        <div className="flex flex-col gap-1">
          <MonoLabel>Keep Controlled</MonoLabel>
          <ul className="flex flex-col gap-0.5 text-sm text-muted-foreground">
            <li>Audience: {projectContext.targetAudience}</li>
            <li>Format: Talking head</li>
            <li>Duration: 45–50s</li>
            <li>CTA: {experiment.cta}</li>
          </ul>
        </div>
      </section>

      <section data-testid="script-editor" className="flex flex-col border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border bg-secondary p-3">
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-muted-foreground" />
            <MonoLabel>Script</MonoLabel>
          </div>
          <Button size="sm" variant="outline" className="gap-1 font-mono text-xs" onClick={copyScript}>
            {copied === "script" ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            {copied === "script" ? "Copied!" : "Copy Script"}
          </Button>
        </div>
        <ul className="flex flex-col">
          {SCRIPT_ROWS.map((r) => (
            <li key={r.segment} className="flex flex-col gap-2 border-b border-border p-4 last:border-b-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-muted-foreground">{r.time}</span>
                  <span className="text-sm font-semibold">{r.segment}</span>
                </div>
                <TagPill tag={r.tag} />
              </div>
              <p className={r.tag === "VARIABLE" ? "border-l-2 border-primary py-1 pl-3 text-sm" : "border-l-2 border-border py-1 pl-3 text-sm text-muted-foreground"}>
                &quot;{scriptContent[r.segment].text}&quot;
              </p>
              {scriptContent[r.segment].note && (
                <p className="pl-3 text-xs italic text-muted-foreground">{scriptContent[r.segment].note}</p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section data-testid="founder-fact-check" className="flex flex-col gap-3 border border-border bg-card p-5">
        <div className="flex items-center gap-2">
          <ShieldAlert className="size-4 text-muted-foreground" />
          <MonoLabel>Founder Fact Check</MonoLabel>
        </div>
        <p className="text-sm">The script says: &quot;{variant.hook}&quot;</p>
        <p className="text-xs text-muted-foreground">Is this accurate? Confirm or edit it — the AI must not invent stories.</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={factState === "confirmed" ? "default" : "outline"} className="gap-1" onClick={() => setFactState("confirmed")}>
            <Check className="size-3.5" /> Yes, accurate
          </Button>
          <Button size="sm" variant="outline" onClick={() => { setInstruction("Rewrite the hook so the facts match what really happened."); setFactState("flagged"); }}>
            Edit hook
          </Button>
          <Button size="sm" variant="outline" onClick={() => setFactState("flagged")}>Remove claim</Button>
        </div>
        {factState === "flagged" && (
          <p className="text-xs text-muted-foreground">Flagged. Use the AI Brief Editor to rewrite the hook without inventing details.</p>
        )}
      </section>

      <section data-testid="recording-guide" className="flex flex-col gap-3 border border-border bg-card p-5">
        <div className="flex items-center gap-2">
          <Camera className="size-4 text-muted-foreground" />
          <MonoLabel>Recording Guide</MonoLabel>
          <span className="rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">Advisory</span>
        </div>
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {RECORDING_GUIDE.map((g) => (
            <li key={g.label} className="flex flex-col gap-1 border border-border p-3">
              <MonoLabel>{g.label}</MonoLabel>
              <span className="text-sm">{g.value}</span>
            </li>
          ))}
        </ul>
      </section>

      <section data-testid="approval-strip" className="flex flex-col gap-3 border border-border bg-card p-5">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="size-4 text-muted-foreground" />
          <MonoLabel>Approval</MonoLabel>
        </div>
        {isLive ? (
          <p className="text-sm text-muted-foreground">This variant is already tracking. <Link href="/videos" className="font-medium text-foreground underline">View metrics</Link>.</p>
        ) : isNext ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={stage === "pending" ? "default" : "outline"}
                className="gap-1"
                onClick={() => setStage(stage === "pending" ? "approved" : "pending")}
              >
                {stage !== "pending" ? <Check className="size-3.5" /> : null}
                Approve for Recording
              </Button>
              {(stage === "approved" || stage === "recorded" || stage === "published") && (
                <Button
                  size="sm"
                  variant={stage === "approved" ? "default" : "outline"}
                  className="gap-1"
                  onClick={() => setStage(stage === "approved" ? "recorded" : "approved")}
                >
                  {stage === "recorded" || stage === "published" ? <Check className="size-3.5" /> : null}
                  I Have Recorded This Variant
                </Button>
              )}
              {(stage === "recorded" || stage === "published") && (
                <Button
                  size="sm"
                  variant={stage === "recorded" ? "default" : "outline"}
                  className="gap-1"
                >
                  {stage === "published" ? <Check className="size-3.5" /> : null}
                  I Have Published This Variant on TikTok
                </Button>
              )}
            </div>
            {stage === "recorded" && (
              <div className="flex flex-col gap-1">
                <MonoLabel>Paste TikTok URL to start tracking</MonoLabel>
                <div className="flex gap-2">
                  <Input
                    value={urlDraft}
                    onChange={(e) => { setUrlDraft(e.target.value); setUrlError(null); }}
                    onKeyDown={(e) => { if (e.key === "Enter") submitUrl(variant.role); }}
                    placeholder="Paste TikTok URL..."
                  />
                  <Button onClick={() => submitUrl(variant.role)}>Start Tracking</Button>
                </div>
                {urlError && <p className="text-xs text-destructive">{urlError}</p>}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">This variant isn&apos;t up next yet. Finish tracking the current variant first.</p>
        )}
      </section>

      <section data-testid="ai-brief-editor" className="flex flex-col border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border bg-secondary p-3">
          <Sparkles className="size-4" />
          <h3 className="text-sm font-semibold">AI Brief Editor</h3>
        </div>
        <div className="flex flex-col gap-4 p-4">
          <p className="text-xs text-muted-foreground">Ask AI to rewrite the hook and delivery for this variant before you shoot.</p>
          <div className="border border-border bg-background p-3">
            <MonoLabel>Current Hook</MonoLabel>
            <p className="mt-1 text-sm font-semibold">&quot;{variant.hook}&quot;</p>
          </div>
          {revision && (
            <div className="flex flex-col gap-2 border border-dashed border-primary p-3">
              <MonoLabel>Proposed Revision</MonoLabel>
              <p className="text-sm font-semibold leading-relaxed">&quot;{revision.hook}&quot;</p>
              <p className="text-xs italic text-muted-foreground">{revision.hookDeliveryNote}</p>
              <div className="mt-1 flex gap-2">
                <Button size="sm" onClick={applyRevision} className="flex-1 font-mono text-[10px] uppercase">Apply</Button>
                <Button size="sm" variant="outline" onClick={discardRevision} className="flex-1 font-mono text-[10px] uppercase">Discard</Button>
              </div>
            </div>
          )}
          <Textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Ask AI to rewrite this hook..."
            className="resize-none font-mono text-xs"
            rows={3}
          />
          <div>
            <MonoLabel>Quick Actions</MonoLabel>
            <div className="mt-2 flex flex-wrap gap-2">
              {QUICK_ACTIONS.map((qa) => (
                <button
                  key={qa}
                  onClick={() => setInstruction(qa)}
                  className="rounded border border-border px-2 py-1 font-mono text-[10px] text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                >
                  {qa}
                </button>
              ))}
            </div>
          </div>
          <Button onClick={rewriteBrief} className="font-mono text-xs">Rewrite Brief</Button>
        </div>
      </section>

      {showPublishModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="publish-check-modal">
          <div className="flex w-full max-w-md flex-col gap-5 border border-border bg-card p-6 shadow-lg">
            <div className="flex flex-col gap-1">
              <MonoLabel>Publication Execution Check</MonoLabel>
              <h3 className="text-lg font-semibold tracking-tight">Confirm before tracking starts</h3>
              <p className="text-sm text-muted-foreground">All three must be true before the tracking window opens.</p>
            </div>
            <div className="flex flex-col gap-3">
              {([
                { key: "videoLive" as const, label: "Video is live at the URL I entered" },
                { key: "variableDelivered" as const, label: "I delivered the variable as written" },
                { key: "controlledPreserved" as const, label: "I did not alter any controlled elements" },
              ]).map(({ key, label }) => (
                <label key={key} className="flex cursor-pointer items-start gap-3" data-testid={`pub-check-${key}`}>
                  <input
                    type="checkbox"
                    checked={pubChecks[key]}
                    onChange={(e) => setPubChecks((prev) => ({ ...prev, [key]: e.target.checked }))}
                    className="mt-0.5 size-4 accent-primary"
                  />
                  <span className="text-sm">{label}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-2">
              <Button
                data-testid="pub-check-confirm"
                onClick={() => confirmPublish(variant!.role)}
                disabled={!pubChecks.videoLive || !pubChecks.variableDelivered || !pubChecks.controlledPreserved}
                className="flex-1"
              >
                Confirm &amp; Start Tracking
              </Button>
              <Button variant="outline" onClick={() => setShowPublishModal(false)} className="flex-1">
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
