import type { Metadata } from "next";
import "./globals.css";

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
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <DemoProvider>
          <NavBar />
          <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
        </DemoProvider>
      </body>
    </html>
  );
}
