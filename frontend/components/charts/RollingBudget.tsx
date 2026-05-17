"use client";
import { useState, useEffect } from "react";

import { API_BASE } from "@/lib/config";

const fmt = (v: number) =>
  v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

// ── Seuils de couleur ─────────────────────────────────────────────────────────
// < 90%   → vert
// 90-100% → amber
// 100-110% → orange
// > 110%  → rouge
const THRESHOLDS = { amber: 0.90, orange: 1.00, red: 1.10 };

type ColorLevel = "green" | "amber" | "orange" | "red";

function getLevel(ratio: number): ColorLevel {
  if (ratio > THRESHOLDS.red)    return "red";
  if (ratio > THRESHOLDS.orange) return "orange";
  if (ratio > THRESHOLDS.amber)  return "amber";
  return "green";
}

const LEVEL_STYLES: Record<ColorLevel, {
  bar: string; barBg: string; text: string; border: string; badge: string; monthBar: string;
}> = {
  green:  {
    bar:      "bg-emerald-500",
    barBg:    "bg-slate-700",
    text:     "text-emerald-400",
    border:   "border-slate-800",
    badge:    "",
    monthBar: "bg-emerald-500/50",
  },
  amber:  {
    bar:      "bg-amber-400",
    barBg:    "bg-amber-900/20",
    text:     "text-amber-400",
    border:   "border-amber-500/20 bg-amber-500/5",
    badge:    "⚠",
    monthBar: "bg-amber-400/60",
  },
  orange: {
    bar:      "bg-orange-500",
    barBg:    "bg-orange-900/20",
    text:     "text-orange-400",
    border:   "border-orange-500/30 bg-orange-500/5",
    badge:    "⚠",
    monthBar: "bg-orange-500/60",
  },
  red:    {
    bar:      "bg-red-500",
    barBg:    "bg-red-900/20",
    text:     "text-red-400",
    border:   "border-red-500/30 bg-red-500/5",
    badge:    "⚠",
    monthBar: "bg-red-500/60",
  },
};

interface MonthData { month: string; total: number }
interface RollingGroup {
  id: number;
  name: string;
  color: string;
  total_period: number;
  monthly_avg: number;
  projected_annual: number;
  budget_annual: number | null;
  budget_monthly: number | null;
  pace_ratio: number | null;
  over_annual: boolean;
  months_data: MonthData[];
}

interface RollingData {
  window_months: number;
  start: string;
  end: string;
  groups: RollingGroup[];
}

interface Props { pivotMonth?: string }

export default function RollingBudget({ pivotMonth }: Props) {
  const [data, setData]         = useState<RollingData | null>(null);
  const [loading, setLoading]   = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ months: "12" });
    if (pivotMonth) params.set("pivot_month", pivotMonth);
    fetch(`${API_BASE}/transactions/summary/rolling?${params}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [pivotMonth]);

  if (loading) return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <p className="text-xs text-slate-500 text-center py-4">Chargement suivi annuel…</p>
    </div>
  );

  if (!data || data.groups.length === 0) return null;

  const groupsWithBudget    = data.groups.filter(g => g.budget_annual);
  const groupsWithoutBudget = data.groups.filter(g => !g.budget_annual && g.total_period > 0);
  const totalSpent   = groupsWithBudget.reduce((s, g) => s + g.total_period, 0);
  const totalBudget  = groupsWithBudget.reduce((s, g) => s + (g.budget_annual ?? 0), 0);
  const overallRatio = totalBudget > 0 ? totalSpent / totalBudget : null;
  const overallLevel = overallRatio !== null ? getLevel(overallRatio) : "green";
  const overallStyles = LEVEL_STYLES[overallLevel];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">Suivi annuel glissant</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            12 mois · {new Date(data.start).toLocaleDateString("fr-FR", { month: "short", year: "numeric" })} → {new Date(data.end).toLocaleDateString("fr-FR", { month: "short", year: "numeric" })}
          </p>
        </div>
        {overallRatio !== null && (
          <div className="text-right">
            <p className="text-xs text-slate-500">Total 12 mois</p>
            <p className="text-sm font-bold text-white">
              {fmt(totalSpent)}{" "}
              <span className="text-slate-500 font-normal">/ {fmt(totalBudget)}</span>{" "}
              <span className={`font-bold ${overallStyles.text}`}>
                {Math.round(overallRatio * 100)}%
              </span>
            </p>
          </div>
        )}
      </div>

      {/* Légende seuils */}
      <div className="flex items-center gap-4 text-[10px] text-slate-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"/>{"< 90%"}</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block"/>90–100%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500 inline-block"/>100–110%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block">{"> 110%"}</span></span>
      </div>

      {/* Groupes avec budget */}
      <div className="space-y-2">
        {groupsWithBudget.map(g => {
          const ratio    = g.pace_ratio ?? 0;
          const level    = getLevel(ratio);
          const styles   = LEVEL_STYLES[level];
          const barWidth = Math.min(ratio * 100, 100);
          const pct      = Math.round(ratio * 100);
          const isOpen   = expanded === g.id;

          return (
            <div key={g.id} className={`rounded-lg border transition-colors ${styles.border}`}>
              <button
                className="w-full text-left px-4 py-3"
                onClick={() => setExpanded(isOpen ? null : g.id)}
              >
                {/* Ligne titre */}
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: g.color }} />
                  <span className="text-xs text-slate-300 flex-1 font-medium">{g.name}</span>

                  {/* Badge alerte */}
                  {level !== "green" && (
                    <span className={`text-[10px] font-medium ${styles.text}`}>{styles.badge}</span>
                  )}

                  {/* Pourcentage bien visible */}
                  <span className={`text-xs tabular-nums font-bold ${styles.text}`}>{pct}%</span>

                  {/* Montants */}
                  <span className={`text-xs tabular-nums font-semibold ${styles.text}`}>
                    {fmt(g.total_period)}
                  </span>
                  <span className="text-xs text-slate-600">/ {fmt(g.budget_annual!)}</span>
                  <span className="text-slate-600 text-xs">{isOpen ? "▲" : "▼"}</span>
                </div>

                {/* Barre avec ticks seuils */}
                <div className={`relative h-2 rounded-full overflow-hidden ${styles.barBg}`}>
                  {/* Fill */}
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${styles.bar}`}
                    style={{ width: `${barWidth}%` }}
                  />
                  {/* Tick 90% */}
                  <div className="absolute top-0 bottom-0 w-px bg-slate-500/50" style={{ left: "90%" }} />
                  {/* Tick 100% (budget exact) */}
                  <div className="absolute top-0 bottom-0 w-px bg-slate-400/70" style={{ left: "99.5%" }} />
                </div>

                {/* Méta */}
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[10px] text-slate-600">
                    Moy. {fmt(g.monthly_avg)}/mois · Budget {fmt(g.budget_monthly!)}/mois
                  </span>
                  <span className={`text-[10px] font-medium ${level !== "green" ? styles.text : "text-slate-600"}`}>
                    {ratio > 1
                      ? `+${fmt(g.total_period - g.budget_annual!)} au-dessus`
                      : `${fmt(g.budget_annual! - g.total_period)} restant`}
                  </span>
                </div>
              </button>

              {/* Détail mensuel */}
              {isOpen && (
                <div className="px-4 pb-3 border-t border-slate-800 pt-3">
                  <div className="grid grid-cols-6 gap-1">
                    {g.months_data.slice(-12).map(m => {
                      const mRatio    = g.budget_monthly ? m.total / g.budget_monthly : 0;
                      const mLevel    = getLevel(mRatio);
                      const mStyles   = LEVEL_STYLES[mLevel];
                      const mBarH     = Math.min(mRatio * 100, 100);
                      const monthLabel = new Date(m.month + "-01").toLocaleDateString("fr-FR", { month: "short" });
                      return (
                        <div key={m.month} className="flex flex-col items-center gap-1">
                          <div className="w-full h-10 bg-slate-800 rounded relative overflow-hidden flex items-end">
                            <div
                              className={`w-full rounded transition-all ${mStyles.monthBar}`}
                              style={{ height: `${Math.max(mBarH, 2)}%` }}
                              title={`${m.month}: ${fmt(m.total)}`}
                            />
                          </div>
                          <span className="text-[9px] text-slate-600">{monthLabel}</span>
                          <span className={`text-[9px] tabular-nums ${mLevel !== "green" ? mStyles.text : "text-slate-500"}`}>
                            {m.total > 0 ? fmt(m.total) : "—"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-slate-600 mt-2 text-right">
                    Projection annuelle : <span className="text-slate-400">{fmt(g.projected_annual)}</span>
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Groupes sans budget */}
      {groupsWithoutBudget.length > 0 && (
        <div className="border-t border-slate-800 pt-3">
          <p className="text-[10px] text-slate-500 mb-2">Sans budget configuré</p>
          <div className="flex flex-wrap gap-2">
            {groupsWithoutBudget.map(g => (
              <div key={g.id} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: g.color }} />
                <span className="text-xs text-slate-400">{g.name}</span>
                <span className="text-xs text-slate-500 tabular-nums">{fmt(g.total_period)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
