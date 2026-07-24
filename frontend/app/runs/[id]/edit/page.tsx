"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, ApiError } from "@/lib/api";
import type { Run, RunType, RunUpdate } from "@/lib/types";

const RUN_TYPES: RunType[] = [
  "easy",
  "long",
  "interval",
  "tempo",
  "recovery",
  "race",
  "other",
];

const FormSchema = z.object({
  date: z.string().min(1),
  run_type: z.enum(RUN_TYPES as [RunType, ...RunType[]]),
  distance_km: z.coerce.number().positive().lt(200),
  duration_hours: z.coerce.number().int().min(0).max(24),
  duration_minutes: z.coerce.number().int().min(0).max(59),
  duration_seconds: z.coerce.number().int().min(0).max(59),
  avg_hr: z.coerce.number().int().gt(30).lt(250).optional().or(z.literal("")),
  perceived_effort: z.coerce
    .number()
    .int()
    .min(1)
    .max(10)
    .optional()
    .or(z.literal("")),
  notes: z.string().max(2000).optional(),
});

type FormInput = z.input<typeof FormSchema>;
type FormOutput = z.output<typeof FormSchema>;

export default function EditRunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [run, setRun] = useState<Run | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const form = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(FormSchema),
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = form;

  useEffect(() => {
    api
      .getRun(id)
      .then((r) => {
        setRun(r);
        const totalSec = r.duration_seconds;
        reset({
          date: r.date,
          run_type: r.run_type,
          distance_km: r.distance_km,
          duration_hours: Math.floor(totalSec / 3600),
          duration_minutes: Math.floor((totalSec % 3600) / 60),
          duration_seconds: totalSec % 60,
          avg_hr: r.avg_hr ?? "",
          perceived_effort: r.perceived_effort ?? "",
          notes: r.notes ?? "",
        });
      })
      .catch((e: ApiError) => setLoadError(e.message));
  }, [id, reset]);

  const onSubmit = async (values: FormOutput) => {
    setSubmitError(null);
    const duration_seconds =
      values.duration_hours * 3600 +
      values.duration_minutes * 60 +
      values.duration_seconds;

    const payload: RunUpdate = {
      date: values.date,
      run_type: values.run_type,
      distance_km: values.distance_km,
      duration_seconds,
      avg_hr: values.avg_hr === "" ? null : (values.avg_hr as number),
      perceived_effort:
        values.perceived_effort === ""
          ? null
          : (values.perceived_effort as number),
      notes: values.notes || null,
    };

    try {
      await api.updateRun(id, payload);
      router.push(`/runs/${id}`);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Update failed.";
      setSubmitError(message);
    }
  };

  if (loadError) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-2xl text-sm text-red-900">
        {loadError}
      </div>
    );
  }
  if (!run) return <div className="text-sand text-sm">Loading…</div>;

  return (
    <div className="max-w-md">
      <h1 className="text-xl font-medium text-ink mb-5">Edit run</h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <Field label="Date" error={errors.date?.message}>
          <input type="date" {...register("date")} className={inputCls} />
        </Field>

        <Field label="Run type" error={errors.run_type?.message}>
          <select {...register("run_type")} className={inputCls}>
            {RUN_TYPES.map((t) => (
              <option key={t} value={t}>
                {t[0].toUpperCase() + t.slice(1)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Distance (km)" error={errors.distance_km?.message}>
          <input
            type="number"
            step="0.01"
            {...register("distance_km")}
            className={inputCls}
          />
        </Field>

        <div>
          <label className="block text-sm font-medium text-clay mb-1">
            Duration
          </label>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Hours" small error={errors.duration_hours?.message}>
              <input
                type="number"
                {...register("duration_hours")}
                className={inputCls}
              />
            </Field>
            <Field
              label="Minutes"
              small
              error={errors.duration_minutes?.message}
            >
              <input
                type="number"
                {...register("duration_minutes")}
                className={inputCls}
              />
            </Field>
            <Field
              label="Seconds"
              small
              error={errors.duration_seconds?.message}
            >
              <input
                type="number"
                {...register("duration_seconds")}
                className={inputCls}
              />
            </Field>
          </div>
        </div>

        <Field label="Average heart rate" error={errors.avg_hr?.message}>
          <input type="number" {...register("avg_hr")} className={inputCls} />
        </Field>

        <Field
          label="Perceived effort 1–10"
          error={errors.perceived_effort?.message}
        >
          <input
            type="number"
            min={1}
            max={10}
            {...register("perceived_effort")}
            className={inputCls}
          />
        </Field>

        <Field label="Notes" error={errors.notes?.message}>
          <textarea {...register("notes")} rows={3} className={inputCls} />
        </Field>

        {submitError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-2xl text-sm text-red-900">
            {submitError}
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={isSubmitting}
            className="bg-leaf-deep text-white px-5 py-2 rounded-full text-sm hover:bg-leaf disabled:bg-leaf-soft disabled:text-leaf-deep/70"
          >
            {isSubmitting ? "Saving…" : "Save changes"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-5 py-2 rounded-full text-sm text-clay border-[0.5px] border-line hover:bg-line/50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

const inputCls =
  "w-full bg-white border-[0.5px] border-line rounded-xl px-3.5 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-leaf/30 focus:border-leaf";

function Field({
  label,
  error,
  small,
  children,
}: {
  label: string;
  error?: string;
  small?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        className={`block ${
          small ? "text-xs" : "text-sm"
        } font-medium text-clay mb-1`}
      >
        {label}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-red-700">{error}</p>}
    </div>
  );
}
