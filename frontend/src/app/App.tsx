import { RouterProvider } from "react-router";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { AppProvider } from "./context/AppContext";
import { RequestsProvider } from "./store/RequestsContext";
import { ListingsProvider } from "./store/ListingsContext";
import { NegotiationProvider } from "./store/NegotiationContext";
import { SellerProfileProvider } from "./store/SellerProfileContext";
import { router } from "./routes";

export default function App() {
  return (
    <AppProvider>
      <RequestsProvider>
        <ListingsProvider>
          <NegotiationProvider>
            <SellerProfileProvider>
              <TooltipProvider delayDuration={200}>
                <RouterProvider router={router} />
                <Toaster />
              </TooltipProvider>
            </SellerProfileProvider>
          </NegotiationProvider>
        </ListingsProvider>
      </RequestsProvider>
    </AppProvider>
  );
}
