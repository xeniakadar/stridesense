import type { Metadata } from "next";
import "./globals.css";

import { BottomNav } from "@/components/BottomNav";
import { DemoProvider } from "@/components/DemoProvider";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "StrideSense",
  description: "Contextual running performance analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-cream text-ink antialiased">
        <DemoProvider>
          <NavBar />
          {/* Mobile-first: one centered column, desktop gets the same */}
          <main className="max-w-md mx-auto px-4 pt-2 pb-28">{children}</main>
          <BottomNav />
        </DemoProvider>
      </body>
    </html>
  );
}
