import { RouterProvider } from "@tanstack/react-router";
import { QueryClientProvider } from "@tanstack/react-query";
import { router } from "./router";
import { ViewerPreferencesProvider } from "./context/viewer-preferences-context";
import { ThemeProvider } from "./context/theme-context";
import { createQueryClient } from "./state/query-client";
import { Toaster } from "./components/ui/sonner";

const queryClient = createQueryClient();

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="qvs-theme">
      <QueryClientProvider client={queryClient}>
        <ViewerPreferencesProvider>
          <RouterProvider router={router} />
          <Toaster />
        </ViewerPreferencesProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
