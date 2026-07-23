import { Label } from "@/components/ui/label";

export function MonoLabel({
  children,
  htmlFor,
}: {
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <Label
      htmlFor={htmlFor}
      className="mb-2 block font-mono text-xs uppercase tracking-wide text-foreground"
    >
      {children}
    </Label>
  );
}
