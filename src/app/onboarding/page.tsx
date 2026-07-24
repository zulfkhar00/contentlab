"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Link2, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  saveProjectContext,
  slugify,
  type ProjectContext,
} from "@/lib/project-context";
import { MonoLabel } from "@/components/mono-label";

const STEPS = [
  {
    num: "01",
    title: "Product Basics",
    desc: "Product name, Product type, Product description, Product URL.",
  },
  {
    num: "02",
    title: "Audience & Problem",
    desc: "Target audience, Problem solved, Why it matters, Current alternatives.",
  },
  {
    num: "03",
    title: "Goal & CTA",
    desc: "Desired action, Primary CTA.",
  },
  {
    num: "04",
    title: "TikTok Setup",
    desc: "TikTok handle, Account is public checkbox, User confirms manual publish.",
  },
  {
    num: "05",
    title: "Tracking Link",
    desc: "",
  },
];

type FormState = Omit<ProjectContext, "trackingSlug" | "destinationUrl">;

const INITIAL_FORM: FormState = {
  productName: "",
  productType: "SaaS",
  productDescription: "",
  productUrl: "",
  targetAudience: "",
  problemSolved: "",
  whyItMatters: "",
  currentAlternatives: "",
  desiredAction: "",
  primaryCta: "",
  tiktokHandle: "",
  accountPublic: false,
  manualPublish: false,
};

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const total = STEPS.length;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const next = () => setStep((s) => Math.min(s + 1, total));
  const back = () => setStep((s) => Math.max(s - 1, 1));

  const trackingSlug = useMemo(
    () => slugify(form.productName) || "founder-lab",
    [form.productName],
  );

  // Each step's required fields must be filled before the user can proceed.
  // Step 5 (Tracking Link) has nothing to fill in, so it's always valid.
  const isStepValid = (() => {
    switch (step) {
      case 1:
        return (
          form.productName.trim().length > 0 &&
          form.productDescription.trim().length > 0 &&
          form.productUrl.trim().length > 0
        );
      case 2:
        return (
          form.targetAudience.trim().length > 0 &&
          form.problemSolved.trim().length > 0 &&
          form.whyItMatters.trim().length > 0 &&
          form.currentAlternatives.trim().length > 0
        );
      case 3:
        return (
          form.desiredAction.trim().length > 0 &&
          form.primaryCta.trim().length > 0
        );
      case 4:
        return (
          form.tiktokHandle.trim().length > 0 &&
          form.accountPublic &&
          form.manualPublish
        );
      default:
        return true;
    }
  })();

  const finish = async () => {
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_name: form.productName,
          product_type: form.productType,
          product_description: form.productDescription,
          product_url: form.productUrl,
          target_audience: form.targetAudience,
          problem_solved: form.problemSolved,
          why_it_matters: form.whyItMatters,
          current_alternatives: form.currentAlternatives,
          desired_action: form.desiredAction,
          primary_cta: form.primaryCta,
          tiktok_handle: form.tiktokHandle,
          account_public: form.accountPublic,
          manual_publish: form.manualPublish,
          onboarded: true,
        }),
      });
      if (res.ok) {
        const project = await res.json();
        saveProjectContext({
          ...form,
          trackingSlug: project.tracking_slug,
          destinationUrl: project.destination_url,
        });
      } else if (res.status !== 409) {
        saveProjectContext({ ...form, trackingSlug, destinationUrl: form.productUrl });
      }
    } catch (err) {
      saveProjectContext({ ...form, trackingSlug, destinationUrl: form.productUrl });
    }
    document.cookie = "cl_onboarded=1; path=/; max-age=31536000; samesite=lax";
    router.push("/overview");
  };

  const copyLink = () => {
    navigator.clipboard?.writeText(`contentlab.app/p/${trackingSlug}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-secondary text-foreground">
      {/* Slim brand header (no app nav during onboarding) */}
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-card px-6">
        <span className="text-base font-semibold tracking-tight">
          Content Lab
        </span>
        <span className="font-mono text-xs text-muted-foreground">
          v0.1-beta
        </span>
      </header>

      <main className="flex flex-1 items-center justify-center overflow-y-auto p-4 md:p-6">
        <div className="flex w-full max-w-[1000px] flex-col border border-border bg-card">
          {/* Card header */}
          <div className="flex items-center justify-between border-b border-border p-6">
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                Project Setup
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Set up your first Content Lab project.
              </p>
            </div>
            <div className="border border-border bg-background px-3 py-1 font-mono text-xs uppercase tracking-wide text-muted-foreground">
              Step {step}/{total}
            </div>
          </div>

          <div className="flex h-[600px] max-h-[70vh] flex-col md:flex-row">
            {/* Stepper */}
            <div className="flex w-full flex-col gap-6 overflow-y-auto border-b border-border bg-card p-6 md:w-1/3 md:border-b-0 md:border-r">
              {STEPS.map((s, i) => {
                const n = i + 1;
                const active = n === step;
                const done = n < step;
                return (
                  <div
                    key={s.num}
                    className={`flex items-start gap-4 ${
                      active ? "" : "opacity-50"
                    }`}
                  >
                    <div
                      className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border-2 bg-card ${
                        active || done ? "border-primary" : "border-border"
                      }`}
                    >
                      <div
                        className={`size-2.5 rounded-full ${
                          active || done ? "bg-primary" : "bg-transparent"
                        }`}
                      />
                    </div>
                    <div>
                      <p className="mb-1 font-mono text-xs">{s.num}</p>
                      <p className="text-sm font-medium">{s.title}</p>
                      {s.desc ? (
                        <p className="mt-1 pr-4 text-xs leading-snug text-muted-foreground">
                          {s.desc}
                        </p>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Content */}
            <div className="w-full overflow-y-auto p-8 md:w-2/3">
              <StepContent
                step={step}
                form={form}
                set={set}
                copied={copied}
                onCopy={copyLink}
                trackingSlug={trackingSlug}
              />
            </div>
          </div>

          {/* Footer */}
          <div className="mt-auto flex items-center justify-between border-t border-border bg-card p-6">
            <Button
              variant="outline"
              onClick={back}
              className={`font-mono text-xs uppercase tracking-wide ${
                step === 1 ? "invisible" : ""
              }`}
            >
              Back
            </Button>
            <Button
              onClick={step === total ? finish : next}
              disabled={!isStepValid}
              className="font-mono text-xs uppercase tracking-wide"
            >
              {step === total ? "Finish Setup" : "Next Step"}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}

function StepContent({
  step,
  form,
  set,
  copied,
  onCopy,
  trackingSlug,
}: {
  step: number;
  form: FormState;
  set: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  copied: boolean;
  onCopy: () => void;
  trackingSlug: string;
}) {
  if (step === 1) {
    return (
      <div>
        <h2 className="mb-8 text-2xl font-semibold tracking-tight">
          Product Basics
        </h2>
        <div className="flex max-w-2xl flex-col gap-6">
          <div>
            <MonoLabel htmlFor="productName">Product Name</MonoLabel>
            <Input
              id="productName"
              placeholder="e.g. Content Lab"
              value={form.productName}
              onChange={(e) => set("productName", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel>Product Type</MonoLabel>
            <Select
              value={form.productType}
              onValueChange={(v) => set("productType", v)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="SaaS">SaaS</SelectItem>
                <SelectItem value="Mobile App">Mobile App</SelectItem>
                <SelectItem value="AI App">AI App</SelectItem>
                <SelectItem value="Service">Service</SelectItem>
                <SelectItem value="Waitlist">Waitlist</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <MonoLabel htmlFor="productDescription">
              Product Description
            </MonoLabel>
            <Textarea
              id="productDescription"
              className="h-24 resize-none"
              placeholder="Briefly describe what your product does..."
              value={form.productDescription}
              onChange={(e) => set("productDescription", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="productUrl">Product URL</MonoLabel>
            <Input
              id="productUrl"
              type="url"
              placeholder="https://"
              value={form.productUrl}
              onChange={(e) => set("productUrl", e.target.value)}
            />
          </div>
        </div>
      </div>
    );
  }

  if (step === 2) {
    return (
      <div>
        <h2 className="mb-8 text-2xl font-semibold tracking-tight">
          Audience & Problem
        </h2>
        <div className="flex max-w-2xl flex-col gap-6">
          <div>
            <MonoLabel htmlFor="targetAudience">Target Audience</MonoLabel>
            <Input
              id="targetAudience"
              placeholder="Who is this for?"
              value={form.targetAudience}
              onChange={(e) => set("targetAudience", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="problemSolved">Problem Solved</MonoLabel>
            <Textarea
              id="problemSolved"
              className="h-24 resize-none"
              placeholder="What pain point does it address?"
              value={form.problemSolved}
              onChange={(e) => set("problemSolved", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="whyItMatters">Why it Matters</MonoLabel>
            <Textarea
              id="whyItMatters"
              className="h-24 resize-none"
              placeholder="Why should they care?"
              value={form.whyItMatters}
              onChange={(e) => set("whyItMatters", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="currentAlternatives">
              Current Alternatives
            </MonoLabel>
            <Textarea
              id="currentAlternatives"
              className="h-24 resize-none"
              placeholder="What are they using now?"
              value={form.currentAlternatives}
              onChange={(e) => set("currentAlternatives", e.target.value)}
            />
          </div>
        </div>
      </div>
    );
  }

  if (step === 3) {
    return (
      <div>
        <h2 className="mb-8 text-2xl font-semibold tracking-tight">
          Goal & CTA
        </h2>
        <div className="flex max-w-2xl flex-col gap-6">
          <div>
            <MonoLabel htmlFor="desiredAction">Desired Action</MonoLabel>
            <Input
              id="desiredAction"
              placeholder="e.g. Sign up for waitlist"
              value={form.desiredAction}
              onChange={(e) => set("desiredAction", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="primaryCta">Primary CTA</MonoLabel>
            <Input
              id="primaryCta"
              placeholder="e.g. Join Beta"
              value={form.primaryCta}
              onChange={(e) => set("primaryCta", e.target.value)}
            />
          </div>
        </div>
      </div>
    );
  }

  if (step === 4) {
    return (
      <div>
        <h2 className="mb-8 text-2xl font-semibold tracking-tight">
          TikTok Setup
        </h2>
        <div className="flex max-w-2xl flex-col gap-6">
          <div>
            <MonoLabel htmlFor="tiktokHandle">TikTok Handle</MonoLabel>
            <div className="flex items-center">
              <span className="flex h-9 items-center border border-r-0 border-border bg-background px-4 font-mono text-sm text-muted-foreground">
                @
              </span>
              <Input
                id="tiktokHandle"
                className="rounded-l-none"
                placeholder="username"
                value={form.tiktokHandle}
                onChange={(e) => set("tiktokHandle", e.target.value)}
              />
            </div>
          </div>
          <label className="flex items-start gap-3">
            <Checkbox
              className="mt-1"
              checked={form.accountPublic}
              onCheckedChange={(c) => set("accountPublic", c === true)}
            />
            <span className="text-sm">My TikTok account is set to public.</span>
          </label>
          <label className="flex items-start gap-3">
            <Checkbox
              className="mt-1"
              checked={form.manualPublish}
              onCheckedChange={(c) => set("manualPublish", c === true)}
            />
            <span className="text-sm">
              I understand I must manually publish generated content to TikTok.
            </span>
          </label>
        </div>
      </div>
    );
  }

  // step === 5
  return (
    <div className="flex h-full flex-col justify-center">
      <div className="mb-6 flex size-12 items-center justify-center border border-border bg-background">
        <Link2 className="size-6 text-muted-foreground" />
      </div>
      <h2 className="mb-4 text-2xl font-semibold tracking-tight">
        Your link is ready
      </h2>
      <p className="mb-6 max-w-md text-sm text-muted-foreground">
        Put this link in your TikTok bio. We record the click, then redirect
        visitors to your product URL.
      </p>
      <div className="mb-6 flex items-center gap-2">
        <div className="flex-1 select-all border border-border bg-background px-4 py-3 font-mono text-xs">
          contentlab.app/p/{trackingSlug}
        </div>
        <Button
          onClick={onCopy}
          className="shrink-0 gap-2 py-3 font-mono text-xs uppercase tracking-wide"
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? "Copied!" : "Copy Tracking Link"}
        </Button>
      </div>
      <div className="inline-flex w-fit items-center gap-2 border border-border bg-background px-3 py-1.5">
        <div className="size-2 rounded-full bg-success" />
        <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
          Link Active
        </span>
      </div>
    </div>
  );
}
