import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function RunFormLoadingSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-full max-w-md" />
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {Array.from({ length: 6 }, (_, index) => `run-form-field-${index}`).map((id) => (
          <div key={id} className="flex flex-col gap-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-full" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
