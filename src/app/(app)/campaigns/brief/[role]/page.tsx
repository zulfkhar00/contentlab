"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Copy, Check, FileText, Sparkles, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  useCampaign,
  getVariant,
  getNextActionVariant,
  variantStatusLabel,
  variantStatusTone,
  isValidTiktokUrl,
  type Variant,
  type VariantRole,
  type VariantBriefEdit,
} from "@/lib/campaign";
import { useProjectContext } from "@/lib/project-context";

const SCRIPT_ROWS = [
  { time: "00–02s", segment: "Hook", tag: "VARIABLE" as const },
  { time: "02–07s", segment: "Context", tag: "VARIABLE" as const },
  { time: "07–25s", segment: "Lesson", tag: "LOCKED" as const },
  { time: "25–40s", segment: "Product", tag: "LOCKED" as const },
  { time: "40–50s", segment: "CTA", tag: "LOCKED" as const },
];

const RECORDING_CHECKLIST = [
  "Vertical orientation (9:16)",
  "Same framing and background as other variants",
  "Look into camera",
  "Clear front lighting and audio",
  "Record hook 3 times",
  "Keep duration within 45–50s",
];

const EDITING_CHECKLIST = [
  "Cut long pauses",
  "Add auto-captions",
  "Keep captions to 3–6 words per line",
  "Use the same caption style as other variants",
  "Emphasize only key phrases",
  "Avoid extra B-roll unless consistent across variants",
];

const PUBLISHING_CHECKLIST = [
  "Use the fixed campaign CTA",
  "Publish manually on TikTok",
];

const QUICK_ACTIONS = ["Make it punchier", "Shorten", "More vulnerable", "More casual"];

// TODO(ai): replace with a real Claude API call once the AI service exists
// (see CONTENT_LAB_PLAN.md phase 3/5). This deterministic transform stands
// in for brief rewriting until that's wired up.
function craftBriefRevision(v: Variant, instruction: string): VariantBriefEdit {
  const trimmed = instruction.trim();
  const angle = trimmed || "a sharper, more specific angle";
  const base = v.hook.replace(/\.$/, "");
  return {
    hook: `${base}, reframed around ${angle}.`,
    hookDeliveryNote: trimmed
      ? `Deliver with ${angle}.`
      : v.hookDeliveryNote,
    context: v.context,
    onScreenText: v.onScreenText,
  };
}

function ChecklistCard({
  icon: Icon,
  title,
  items,
  checked,
  onToggle,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  items: string[];
  checked: Record<number, boolean>;
  onToggle: (i: number) => void;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col border border-border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="size-4 text-muted-foreground" />
        <h4 className="font-mono text-xs uppercase tracking-wide">{title}</h4>
      </div>
      <ul className="flex flex-1 flex-col gap-2">
        {items.map((item, i) => (
          <li key={item} className="flex items-start gap-2">
            <Checkbox
              className="mt-0.5"
              checked={!!checked[i]}
              onCheckedChange={() => onToggle(i)}
            />
            <span className="text-sm text-muted-foreground">{item}</span>
          </li>
        ))}
      </ul>
      {children}
    </div>
  );
}

export default function RecordingBriefPage() {
  const params = useParams<{ role: string }>();
  const { campaign, startTracking, updateVariantBrief } = useCampaign();
  const { context: projectContext } = useProjectContext();
  const variant = getVariant(campaign, params.role);
  const nextVariant = getNextActionVariant(campaign.variants);

  const [recordingChecked, setRecordingChecked] = useState<Record<number, boolean>>({});
  const [editingChecked, setEditingChecked] = useState<Record<number, boolean>>({});
  const [publishingChecked, setPublishingChecked] = useState<Record<number, boolean>>({});
  const [urlDraft, setUrlDraft] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const [revision, setRevision] = useState<VariantBriefEdit | null>(null);

  if (!variant) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          No variant found for &quot;{params.role}&quot;.
        </p>
        <Button asChild variant="outline" className="w-fit gap-2">
          <Link href="/campaigns">
            <ArrowLeft className="size-4" />
            Back to Campaign
          </Link>
        </Button>
      </div>
    );
  }

  const isNext = variant.role === nextVariant?.role;
  const isLive = variant.status === "tracking" || variant.status === "completed";

  const scriptContent: Record<string, { text: string; note?: string }> = {
    Hook: { text: variant.hook, note: variant.hookDeliveryNote },
    Context: { text: variant.context },
    Lesson: { text: campaign.script.lesson },
    Product: { text: campaign.script.product },
    CTA: { text: campaign.script.cta },
  };

  function copy(label: string, text: string) {
    navigator.clipboard?.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  }

  function copyScript() {
    const text = SCRIPT_ROWS.map(
      (r) => `${r.segment} (${r.time}): "${scriptContent[r.segment].text}"`,
    ).join("\n");
    copy("script", text);
  }

  function submitUrl(role: VariantRole) {
    const trimmed = urlDraft.trim();
    if (!isValidTiktokUrl(trimmed)) {
      setUrlError("Paste a valid TikTok video URL (https://tiktok.com/...).");
      return;
    }
    setUrlError(null);
    startTracking(role, trimmed);
    setUrlDraft("");
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

  function discardRevision() {
    setRevision(null);
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
          <Link
            href="/campaigns"
            className="flex items-center gap-1 hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />
            Back to Campaign
          </Link>
          <span className="text-border">/</span>
          <span>Variant {variant.role}</span>
        </div>
        <span
          className={`rounded px-2.5 py-1 font-mono text-xs uppercase tracking-wide ${
            variantStatusTone(variant.status) === "active"
              ? "border border-success/20 bg-[#ECFDF5] text-success"
              : "border border-border bg-card text-muted-foreground"
          }`}
        >
          {variantStatusLabel(variant.status)}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Campaign: {campaign.name}
        </span>
        <span className="w-fit rounded border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
          {variant.roleLabel}
        </span>
        <h2 className="text-2xl font-semibold tracking-tight">
          Variant {variant.role} — {variant.title}
        </h2>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Main canvas */}
        <div className="flex flex-col gap-6 lg:col-span-9">
          {/* The Hook */}
          <div className="border border-border bg-card p-6">
            <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
              <FileText className="size-5" />
              <h3 className="font-mono text-xs uppercase">The Hook</h3>
            </div>
            <p className="text-lg font-semibold leading-relaxed">
              &quot;{variant.hook}&quot;
            </p>
          </div>

          {/* Script sequence */}
          <div className="border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border bg-secondary px-4 py-3">
              <h3 className="font-mono text-xs uppercase">Script Sequence</h3>
              <span className="font-mono text-xs text-muted-foreground">
                Target Duration: {campaign.script.targetDurationLabel}
              </span>
            </div>
            <table className="w-full border-collapse text-left">
              <thead>
                <tr>
                  <th className="w-24 border-b border-border p-4 font-mono text-xs text-muted-foreground">
                    Time
                  </th>
                  <th className="w-32 border-b border-border p-4 font-mono text-xs text-muted-foreground">
                    Segment
                  </th>
                  <th className="border-b border-border p-4 font-mono text-xs text-muted-foreground">
                    Content / Delivery Notes
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-sm">
                {SCRIPT_ROWS.map((row) => {
                  const content = scriptContent[row.segment];
                  return (
                    <tr key={row.segment} className="hover:bg-secondary/50">
                      <td className="p-4 align-top font-mono text-xs text-muted-foreground">
                        {row.time}
                      </td>
                      <td className="p-4 align-top">
                        <div className="flex flex-col gap-1">
                          <span className="w-fit rounded bg-secondary px-2 py-1 text-xs font-medium">
                            {row.segment}
                          </span>
                          <span className="font-mono text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                            {row.tag === "VARIABLE"
                              ? "Variable"
                              : "Locked Across Variants"}
                          </span>
                        </div>
                      </td>
                      <td className="p-4 align-top">
                        &quot;{content.text}&quot;
                        {content.note && (
                          <span className="mt-1 block text-sm italic text-muted-foreground">
                            {content.note}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Checklists */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <ChecklistCard
              icon={Play}
              title="Recording"
              items={RECORDING_CHECKLIST}
              checked={recordingChecked}
              onToggle={(i) =>
                setRecordingChecked((c) => ({ ...c, [i]: !c[i] }))
              }
            />
            <ChecklistCard
              icon={FileText}
              title="Editing"
              items={EDITING_CHECKLIST}
              checked={editingChecked}
              onToggle={(i) => setEditingChecked((c) => ({ ...c, [i]: !c[i] }))}
            >
              <div className="mt-4 border-t border-border pt-4">
                <div className="mb-3 flex items-center gap-2">
                  <FileText className="size-4 text-muted-foreground" />
                  <h4 className="font-mono text-xs uppercase tracking-wide">
                    On-Screen Text
                  </h4>
                </div>
                <div className="mb-3">
                  <span className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    Opening Text
                  </span>
                  <div className="border border-border bg-secondary p-2 text-sm">
                    &quot;{variant.onScreenText}&quot;
                  </div>
                </div>
                <ul className="flex flex-col gap-1.5 text-sm text-muted-foreground">
                  <li>Auto-captions</li>
                  <li>3–6 words per line</li>
                  <li>Same font and placement across variants</li>
                </ul>
              </div>
            </ChecklistCard>
            <ChecklistCard
              icon={FileText}
              title="Publishing"
              items={PUBLISHING_CHECKLIST}
              checked={publishingChecked}
              onToggle={(i) =>
                setPublishingChecked((c) => ({ ...c, [i]: !c[i] }))
              }
            />
          </div>

          {/* Tracking action */}
          <div className="flex flex-col items-end gap-4 border border-border bg-card p-5 md:flex-row">
            {isLive ? (
              <p className="flex-1 text-sm text-muted-foreground">
                This variant is already tracking.{" "}
                <Link href="/videos" className="font-medium text-foreground underline">
                  View metrics
                </Link>
                .
              </p>
            ) : isNext ? (
              <>
                <div className="w-full flex-1">
                  <label className="mb-2 block font-mono text-xs text-foreground">
                    Track Distribution Performance
                  </label>
                  <Input
                    value={urlDraft}
                    onChange={(e) => {
                      setUrlDraft(e.target.value);
                      setUrlError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitUrl(variant.role);
                    }}
                    placeholder="Paste TikTok URL..."
                  />
                  {urlError && (
                    <p className="mt-1 text-xs text-destructive">{urlError}</p>
                  )}
                </div>
                <Button
                  className="w-full gap-2 md:w-auto"
                  onClick={() => submitUrl(variant.role)}
                >
                  <Play className="size-4" />
                  Start Tracking
                </Button>
              </>
            ) : (
              <p className="flex-1 text-sm text-muted-foreground">
                This variant isn&apos;t up next yet. Finish tracking the current
                variant first.
              </p>
            )}
          </div>
        </div>

        {/* Right sidebar */}
        <div className="flex flex-col gap-4 lg:col-span-3">
          <div className="flex flex-col gap-3 border border-border bg-card p-4">
            <h4 className="border-b border-border pb-2 font-mono text-xs uppercase tracking-wide text-muted-foreground">
              Experiment Context
            </h4>
            <div>
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Role
              </span>
              <span className="w-fit rounded border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                {variant.roleLabel}
              </span>
            </div>
            <div>
              <span className="mb-0.5 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Variable Under Test
              </span>
              <span className="text-sm">{variant.variableUnderTest}</span>
            </div>
            <div>
              <span className="mb-0.5 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Primary Metric
              </span>
              <span className="text-sm">{campaign.primaryMetric}</span>
            </div>
            <div className="border-t border-border pt-2">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Keep Constant
              </span>
              <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                <li>Audience: {projectContext.targetAudience}</li>
                <li>Format: Talking head</li>
                <li>Duration: 45–50s</li>
                <li>CTA: {campaign.cta}</li>
              </ul>
            </div>
          </div>

          <div className="flex flex-col gap-2 border border-border bg-card p-4">
            <h4 className="mb-1 border-b border-border pb-2 font-mono text-xs uppercase tracking-wide text-muted-foreground">
              Quick Actions
            </h4>
            <Button
              variant="outline"
              className="justify-start gap-2"
              onClick={() => copy("hook", variant.hook)}
            >
              {copied === "hook" ? (
                <Check className="size-4" />
              ) : (
                <Copy className="size-4" />
              )}
              {copied === "hook" ? "Copied!" : "Copy Hook"}
            </Button>
            <Button
              variant="outline"
              className="justify-start gap-2"
              onClick={copyScript}
            >
              {copied === "script" ? (
                <Check className="size-4" />
              ) : (
                <FileText className="size-4" />
              )}
              {copied === "script" ? "Copied!" : "Copy Script"}
            </Button>
          </div>

          {/* AI Brief Editor */}
          <div className="flex flex-col border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border bg-secondary px-4 py-3">
              <Sparkles className="size-4" />
              <h3 className="text-sm font-semibold">AI Brief Editor</h3>
            </div>
            <div className="flex flex-col gap-4 p-4">
              <p className="text-xs text-muted-foreground">
                Ask AI to rewrite the hook and delivery for this variant before
                you record.
              </p>

              <div className="relative border border-border bg-background p-3">
                <span className="absolute -top-2 left-2 bg-card px-1 font-mono text-[10px] text-muted-foreground">
                  CURRENT HOOK
                </span>
                <p className="text-sm font-semibold">&quot;{variant.hook}&quot;</p>
              </div>

              {revision && (
                <div className="relative flex flex-col gap-3 border border-dashed border-primary p-3">
                  <span className="absolute -top-2 left-2 bg-card px-1 font-mono text-[10px] font-bold text-foreground">
                    PROPOSED REVISION
                  </span>
                  <p className="text-sm font-semibold leading-relaxed">
                    &quot;{revision.hook}&quot;
                  </p>
                  <p className="text-xs italic text-muted-foreground">
                    {revision.hookDeliveryNote}
                  </p>
                  <div className="mt-1 flex gap-2">
                    <Button
                      size="sm"
                      className="flex-1 font-mono text-[10px] uppercase"
                      onClick={applyRevision}
                    >
                      Apply
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1 font-mono text-[10px] uppercase"
                      onClick={discardRevision}
                    >
                      Discard
                    </Button>
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
                <span className="mb-2 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  Quick Actions
                </span>
                <div className="flex flex-wrap gap-2">
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

              <Button onClick={rewriteBrief} className="font-mono text-xs">
                Rewrite Brief
              </Button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
