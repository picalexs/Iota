import { createRouter } from "@tanstack/react-router";

import { NotFoundPage, routeTree } from "@/routes";

export const router = createRouter({ routeTree, defaultNotFoundComponent: NotFoundPage });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
