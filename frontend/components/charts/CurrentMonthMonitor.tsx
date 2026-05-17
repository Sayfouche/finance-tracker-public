"use client";

const fmt = (v: number) =>
  v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

interface GroupData {
  name: string;
  color: string;
  total: number;
  budget_monthly: number | null;
  over_limit: boolean;
  projection_mode: "linear" | "fixed_historical" | "actual_only";
  projection_amount: number;
  projection_over_limit: boolean;
  projection_source: string;
  projection_reference: number | null;
}

interface Props {
  groups: GroupData[];
  depenses: number;
  days_elapsed: number;
  days_in_month: number;
}

export default function CurrentMonthMonitor({ groups, depenses, days_elapsed, days_in_month }: Props) {
  const days_remaining = days_in_month - days_elapsed;
  const projected_total = Math.round(groups.reduce((sum, g) => sum + (g.projection_amount ?? g.total), 0));
  const progress_pct   = Math.round((days_elapsed / days_in_month) * 100);

  // Budget total mensuel configuré
  const total_budget = groups.reduce((s, g) => s + (g.budget_monthly ?? 0), 0);
  const projected_over = total_budget > 0 && projected_total > total_budget;
  const groups_with_budget = groups.filter(g => g.budget_monthly);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">Mois en cours</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Jour {days_elapsed} / {days_in_month} — {days_remaining} jours restants
          </p>
        </div>
        {projected_over && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/20 text-red-400">
            ⚠ Dépassement prévu
          </span>
        )}
      </div>

      {/* Barre de progression du mois */}
      <div>
        <div className="flex justify-between text-[10px] text-slate-500 mb-1">
          <span>Avancement du mois</span>
          <span>{progress_pct}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <div className="h-full rounded-full bg-slate-600" style={{ width: `${progress_pct}%` }} />
        </div>
      </div>

      {/* KPI pace global */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-slate-800/60 rounded-lg p-3 text-center">
          <p className="text-[10px] text-slate-500 mb-1">Dépensé</p>
          <p className="text-sm font-bold text-white">{fmt(depenses)}</p>
        </div>
        <div className={`rounded-lg p-3 text-center ${projected_over ? "bg-red-500/10 border border-red-500/20" : "bg-slate-800/60"}`}>
          <p className="text-[10px] text-slate-500 mb-1">Projection fin de mois</p>
          <p className={`text-sm font-bold ${projected_over ? "text-red-400" : "text-amber-400"}`}>{fmt(projected_total)}</p>
        </div>
        <div className="bg-slate-800/60 rounded-lg p-3 text-center">
          <p className="text-[10px] text-slate-500 mb-1">Budget mensuel</p>
          <p className="text-sm font-bold text-indigo-400">{total_budget > 0 ? fmt(total_budget) : "—"}</p>
        </div>
      </div>

      {/* Par groupe */}
      {groups_with_budget.length > 0 && (
        <div className="space-y-2">
          {groups_with_budget.map((g, i) => {
            const budget    = g.budget_monthly!;
            const spent_pct = Math.min(Math.round(g.total / budget * 100), 100);
            const projected = Math.round(g.projection_amount ?? g.total);
            const proj_pct  = Math.min(Math.round(projected / budget * 100), 100);
            const over_now  = g.over_limit;
            const over_proj = g.projection_over_limit;
            const bar_color = over_now ? "bg-red-500" : over_proj ? "bg-amber-400" : spent_pct > 70 ? "bg-amber-400/60" : "bg-emerald-500";
            const projectionLabel =
              g.projection_source === "pace" ? "lissé" :
              g.projection_source === "historical_6m" ? "moy. 6 mois" :
              g.projection_source === "actual_paid" ? "paiement constaté" :
              "réel";

            return (
              <div key={i} className={`rounded-lg px-3 py-2.5 ${over_now ? "bg-red-500/5 border border-red-500/20" : "bg-slate-800/40"}`}>
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: g.color }} />
                  <span className="text-xs text-slate-300 flex-1">{g.name}</span>
                  {over_now && <span className="text-[10px] text-red-400">dépassé</span>}
                  {!over_now && over_proj && <span className="text-[10px] text-amber-400">↗ prévu dépassement</span>}
                  <span className={`text-xs tabular-nums font-medium ${over_now ? "text-red-400" : "text-slate-300"}`}>
                    {fmt(g.total)}
                  </span>
                  <span className="text-xs text-slate-600">/ {fmt(budget)}</span>
                </div>

                {/* Double barre : dépensé + projection */}
                <div className="relative h-1.5 rounded-full bg-slate-700 overflow-hidden">
                  {/* Projection (en transparence derrière) */}
                  <div
                    className={`absolute inset-y-0 left-0 rounded-full opacity-30 ${bar_color}`}
                    style={{ width: `${proj_pct}%` }}
                  />
                  {/* Dépensé réel */}
                  <div
                    className={`absolute inset-y-0 left-0 rounded-full ${bar_color}`}
                    style={{ width: `${spent_pct}%` }}
                  />
                </div>

                <div className="flex justify-between mt-1">
                  <span className="text-[9px] text-slate-600">
                    Projection : {fmt(projected)} · {projectionLabel}
                  </span>
                  <span className={`text-[9px] ${over_proj ? "text-amber-400" : "text-slate-600"}`}>
                    {over_proj ? `+${fmt(projected - budget)} prévu` : `${fmt(budget - projected)} de marge`}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
