import { SITE_NAME } from "@/lib/site-metadata";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t px-6 py-4 text-center text-xs text-muted-foreground">
      © {year} {SITE_NAME}
    </footer>
  );
}
