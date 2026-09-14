import { cn } from "@/lib/utils";

type FormErrorProps = Readonly<{
  message?: string | null;
  className?: string;
}>;

export function FormError({ message, className }: FormErrorProps) {
  if (message) {
    return (
      <p role="alert" className={cn("text-destructive text-sm", className)}>
        {message}
      </p>
    );
  }

  return null;
}
