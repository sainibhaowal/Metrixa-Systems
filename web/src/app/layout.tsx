import type { Metadata } from "next";
import "./globals.css";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { StickyTopbar } from "@/components/layout/StickyTopbar";
import { SidebarProvider } from "@/components/layout/SidebarContext";

export const metadata: Metadata = {
  title: "Heidi Cockpit — Autonomous LeadOps & Metering Intelligence",
  description: "Enterprise GTM Intelligence Cockpit for Heidi Systems GmbH (Berlin Property Management Companies)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-zinc-100 flex min-h-screen antialiased">
        <SidebarProvider>
          <SidebarNav />
          <div className="flex-1 flex flex-col min-w-0 transition-all duration-300 ease-in-out">
            <StickyTopbar />
            <main className="flex-1 p-3 sm:p-5 lg:p-6 overflow-y-auto">
              {children}
            </main>
          </div>
        </SidebarProvider>
      </body>
    </html>
  );
}
