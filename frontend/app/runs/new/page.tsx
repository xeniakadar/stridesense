"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, ApiError } from "@/lib/api";
import type { RunCreate, RunType } from "@/lib/types";

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
  date: z.string().min(1, "Required"),
  run_type: z.enum(RUN_TYPES as [RunType, ...RunType[]]),
  distance_km: z.coerce
    .number()
    .positive("Must be positive")
    .lt(200, "Too large"),
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

export default function NewRunPage() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(FormSchema),
    defaultValues: {
      date: new Date().toISOString().slice(0, 10),
      run_type: "easy",
      distance_km: "" as unknown as number,
      duration_hours: "" as unknown as number,
      duration_minutes: 30 as unknown as number,
      duration_seconds: "" as unknown as number,
    },
  });

  const onSubmit = async (values: FormOutput) => {
    setSubmitError(null);
    const duration_seconds =
      values.duration_hours * 3600 +
      values.duration_minutes * 60 +
      values.duration_seconds;

    if (duration_seconds <= 0) {
      setSubmitError("Duration must be greater than zero.");
      return;
    }

    const payload: RunCreate = {
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
      const run = await api.createRun(payload);
      router.push(`/runs/${run.id}`);
    } catch (e) {
      const message =
        e instanceof ApiError ? e.message : "Something went wrong.";
      setSubmitError(message);
    }
  };

  return (
    <div className="max-w-md">
      <h1 className="text-xl font-medium text-ink mb-5">Add a run</h1>

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
            inputMode="decimal"
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

        <Field
          label="Average heart rate (optional)"
          error={errors.avg_hr?.message}
        >
          <input type="number" {...register("avg_hr")} className={inputCls} />
        </Field>

        <Field
          label="Perceived effort 1–10 (optional)"
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

        <Field label="Notes (optional)" error={errors.notes?.message}>
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
            className="tap-target bg-leaf-deep text-white px-5 py-2 rounded-full text-sm hover:bg-leaf disabled:bg-leaf-soft disabled:text-leaf-deep/70"
          >
            {isSubmitting ? "Saving…" : "Save run"}
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
