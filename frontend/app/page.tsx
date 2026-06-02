"use client";

import { useEffect, useState } from "react";

type HealthResponse = { status: string; db?: string };

export default function Home() {
  const [apiHealth, setApiHealth] = useState<HealthResponse | null>(null);
  const [dbHealth, setDbHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    fetch(`${apiUrl}/health`)
      .then((r) => r.json())
      .then(setApiHealth)
      .catch((e) => setError(String(e)));

    fetch(`${apiUrl}/health/db`)
      .then((r) => r.json())
      .then(setDbHealth)
      .catch(() => {});
  }, []);

  return (
    <main className="min-h-screen p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-medium mb-2">StrideSense</h1>
      <p className="text-gray-600 mb-8">Phase 0 — scaffolding check</p>

      <div className="space-y-4">
        <HealthRow label="Frontend → Backend" data={apiHealth} />
        <HealthRow label="Backend → Postgres" data={dbHealth} />
      </div>

      {error && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded text-sm text-red-900">
          {error}
        </div>
      )}
    </main>
  );
}

function HealthRow({
  label,
  data,
}: {
  label: string;
  data: HealthResponse | null;
}) {
  const ok = data?.status === "ok";
  return (
    <div className="flex items-center justify-between p-4 border rounded">
      <span>{label}</span>
      <span className={ok ? "text-green-600" : "text-gray-400"}>
        {ok ? "✓ ok" : "…"}
      </span>
    </div>
  );
}
