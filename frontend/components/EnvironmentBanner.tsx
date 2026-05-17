import { APP_ENV, DATASET_LABEL } from "@/lib/config";

export default function EnvironmentBanner() {
  const isProd = APP_ENV === "local-prod" || APP_ENV === "prod";
  const label = isProd ? DATASET_LABEL : DATASET_LABEL || "Compte demo - donnees mockees";

  return (
    <div
      className={`border-b px-4 py-2 text-center text-xs font-semibold uppercase tracking-wide ${
        isProd
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
          : "border-amber-500/30 bg-amber-500/10 text-amber-200"
      }`}
    >
      {isProd ? "Local prod" : "Demo / Dev"} · {label}
    </div>
  );
}
