import type { Metadata, Viewport } from "next";
import "./globals.css";

import { BottomNav } from "@/components/BottomNav";
import { DemoProvider } from "@/components/DemoProvider";
import { NavBar } from "@/components/NavBar";
import { PresentationAside } from "@/components/PresentationAside";

export const metadata: Metadata = {
  title: "StrideSense",
  description: "Contextual running performance analysis",
};

// cover + safe-area insets: the UI extends under the iPhone notch and
// home indicator, and the nav bars pad themselves clear of both
export const viewport: Viewport = {
  viewportFit: "cover",
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
          {/* Presentation shell: inert below 900px (the app renders
              full-bleed exactly as before); above it, the app sits in a
              phone frame with an info column. Styles live in globals.css. */}
          <div className="shell">
            <PresentationAside />
            {/* On desktop the frame is a fixed-height flex column: the
                screen is the flex:1 scroll region and the bottom nav is
                its non-shrinking sibling — pinned to the frame's bottom
                on every page, however short the content */}
            <div className="phone-frame">
              <div className="phone-screen">
                <NavBar />
                {/* Mobile-first: one centered column, desktop gets the same */}
                <main className="max-w-md mx-auto px-4 pt-2 pb-28">
                  {children}
                </main>
              </div>
              <BottomNav />
            </div>
          </div>
        </DemoProvider>
      </body>
    </html>
  );
}
