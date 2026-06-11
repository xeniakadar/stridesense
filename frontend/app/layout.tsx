import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

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
        <header className="border-b border-gray-200 bg-white">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link href="/" className="text-lg font-medium">
              StrideSense
            </Link>
            <nav className="flex gap-6 text-sm text-gray-600">
              <Link href="/" className="hover:text-gray-900">
                Dashboard
              </Link>
              <Link href="/runs" className="hover:text-gray-900">
                Runs
              </Link>
              <Link
                href="/runs/new"
                className="text-white bg-gray-900 hover:bg-gray-700 px-3 py-1.5 rounded"
              >
                + Add run
              </Link>
            </nav>
          </div>
        </header>
        <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
