import type { Metadata } from "next";
import "./globals.css";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { StickyTopbar } from "@/components/layout/StickyTopbar";
import { SidebarProvider } from "@/components/layout/SidebarContext";

export const metadata: Metadata = {
  title: "Metrixa Cockpit :  Autonomous LeadOps & Metering Intelligence",
  description:
    "Enterprise GTM Intelligence Cockpit for Metrixa Systems GmbH (Berlin Property Management Companies)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-zinc-100 flex h-screen overflow-hidden antialiased">
        <SidebarProvider>
          <SidebarNav />
          <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden transition-all duration-300 ease-in-out">
            <StickyTopbar />
            <main className="flex-1 flex flex-col min-h-0 px-3 pb-3 overflow-y-auto">
              {children}
            </main>
          </div>
        </SidebarProvider>
      </body>
    </html>
  );
}
