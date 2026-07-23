"use client";

import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
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
import { MonoLabel } from "@/components/mono-label";
import {
  useProjectContext,
  type ProjectContext,
} from "@/lib/project-context";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col border border-border bg-card">
      <div className="border-b border-border bg-secondary px-4 py-3">
        <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      </div>
      <div className="flex flex-col gap-6 p-6">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { context, setContext, loaded } = useProjectContext();
  const [draft, setDraft] = useState<ProjectContext>(context);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);

  // Seed the editable draft once the real (persisted) context has loaded.
  useEffect(() => {
    if (loaded) setDraft(context);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  const set = <K extends keyof ProjectContext>(
    key: K,
    value: ProjectContext[K],
  ) => setDraft((d) => ({ ...d, [key]: value }));

  const trackingLink = `contentlab.app/p/${draft.trackingSlug}`;

  const copyLink = () => {
    navigator.clipboard?.writeText(trackingLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const saveChanges = () => {
    setContext(draft);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!loaded) return null;

  return (
    <>
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Settings</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Product context, TikTok account, and tracking link for this project.
        </p>
      </div>

      <div className="flex max-w-3xl flex-col gap-4">
        <Section title="Project Details">
          <div>
            <MonoLabel htmlFor="productName">Product Name</MonoLabel>
            <Input
              id="productName"
              value={draft.productName}
              onChange={(e) => set("productName", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel>Product Type</MonoLabel>
            <Select
              value={draft.productType}
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
              value={draft.productDescription}
              onChange={(e) => set("productDescription", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="productUrl">Product Website</MonoLabel>
            <Input
              id="productUrl"
              type="url"
              value={draft.productUrl}
              onChange={(e) => set("productUrl", e.target.value)}
            />
          </div>
        </Section>

        <Section title="Project Context">
          <div>
            <MonoLabel htmlFor="targetAudience">Target Audience</MonoLabel>
            <Input
              id="targetAudience"
              value={draft.targetAudience}
              onChange={(e) => set("targetAudience", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="problemSolved">Problem Solved</MonoLabel>
            <Textarea
              id="problemSolved"
              className="h-24 resize-none"
              value={draft.problemSolved}
              onChange={(e) => set("problemSolved", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="whyItMatters">Why it Matters</MonoLabel>
            <Textarea
              id="whyItMatters"
              className="h-24 resize-none"
              value={draft.whyItMatters}
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
              value={draft.currentAlternatives}
              onChange={(e) => set("currentAlternatives", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="desiredAction">Desired Action</MonoLabel>
            <Input
              id="desiredAction"
              value={draft.desiredAction}
              onChange={(e) => set("desiredAction", e.target.value)}
            />
          </div>
          <div>
            <MonoLabel htmlFor="primaryCta">Primary CTA</MonoLabel>
            <Input
              id="primaryCta"
              value={draft.primaryCta}
              onChange={(e) => set("primaryCta", e.target.value)}
            />
          </div>
        </Section>

        <Section title="TikTok Account">
          <div>
            <MonoLabel htmlFor="tiktokHandle">TikTok Handle</MonoLabel>
            <div className="flex items-center">
              <span className="flex h-9 items-center border border-r-0 border-border bg-background px-4 font-mono text-sm text-muted-foreground">
                @
              </span>
              <Input
                id="tiktokHandle"
                className="rounded-l-none"
                value={draft.tiktokHandle}
                onChange={(e) => set("tiktokHandle", e.target.value)}
              />
            </div>
          </div>
          <label className="flex items-start gap-3">
            <Checkbox
              className="mt-1"
              checked={draft.accountPublic}
              onCheckedChange={(c) => set("accountPublic", c === true)}
            />
            <span className="text-sm">My TikTok account is set to public.</span>
          </label>
          <label className="flex items-start gap-3">
            <Checkbox
              className="mt-1"
              checked={draft.manualPublish}
              onCheckedChange={(c) => set("manualPublish", c === true)}
            />
            <span className="text-sm">
              I understand I must manually publish generated content to TikTok.
            </span>
          </label>
        </Section>

        <Section title="Tracking & Redirect">
          <div>
            <MonoLabel>Permanent Tracking Link</MonoLabel>
            <div className="flex items-center gap-2">
              <div className="flex-1 select-all border border-border bg-background px-4 py-2 font-mono text-xs text-muted-foreground">
                {trackingLink}
              </div>
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={copyLink}
                aria-label="Copy tracking link"
              >
                {copied ? (
                  <Check className="size-4" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              This link never changes. Update the destination URL below to
              change where it redirects — that only affects future clicks.
            </p>
          </div>
          <div>
            <MonoLabel htmlFor="destinationUrl">Destination URL</MonoLabel>
            <Input
              id="destinationUrl"
              type="url"
              value={draft.destinationUrl}
              onChange={(e) => set("destinationUrl", e.target.value)}
            />
          </div>
        </Section>

        <div className="flex items-center justify-end gap-3 pb-8">
          {saved && (
            <span className="font-mono text-xs uppercase tracking-wide text-success">
              Saved
            </span>
          )}
          <Button onClick={saveChanges}>Save Changes</Button>
        </div>
      </div>
    </>
  );
}
