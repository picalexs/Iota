import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";
import { FormError } from "./form-error";
import { FieldHelp } from "./field-help";

type FieldHelpConfig = Readonly<{
  short: string;
  anchor?: string;
  href?: string;
}>;

type FormFieldProps = Readonly<{
  label: string;
  htmlFor: string;
  children: ReactNode;
  error?: string | null;
  required?: boolean;
  help?: FieldHelpConfig;
  labelAction?: ReactNode;
}>;

export function FormField({
  label,
  htmlFor,
  children,
  error,
  required = false,
  help,
  labelAction,
}: FormFieldProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Label htmlFor={htmlFor}>
          {label}
          {required && <span className="text-destructive">*</span>}
        </Label>
        {help && (
          <FieldHelp short={help.short} anchor={help.anchor} href={help.href} label={label} />
        )}
        {labelAction && <div className="ml-auto">{labelAction}</div>}
      </div>
      {children}
      <FormError message={error} />
    </div>
  );
}
