"use client";
import { useState, useEffect } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

import { API_BASE } from "@/lib/config";

interface CategoryData { id?: number; name: string; color: string; total: number }
interface GroupData    { name: string; color: string; total: number; categories: CategoryData[]; budget_annual?: number | null; budget_monthly?: number | null; over_limit?: boolean }
interface TxItem      { id: number; date: string; label: string; amount: number; type: string }
const fmt    = (v: number) => v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const fmtFull= (v: number) => v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
const FALLBACK: CategoryData[] = [{ name: "Aucune donnée", color: "#334155", total: 1 }];

type Level = "groups" | "categories" | "transactions";

interface Props {
  categories: CategoryData[];
  groups: GroupData[];
  month: string;
}

export default function ExpensesByCategory({ categories, groups, month }: Props) {
  const [view, setView]               = useState<"groups" | "detail">("groups");
  const [level, setLevel]             = useState<Level>("groups");
  const [drillGroup, setDrillGroup]   = useState<GroupData | null>(null);
  const [drillCat, setDrillCat]       = useState<CategoryData | null>(null);
  const [txs, setTxs]                 = useState<TxItem[]>([]);
  const [txLoading, setTxLoading]     = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [mounted, setMounted]         = useState(false);
  useEffect(() => setMounted(true), []);

  const pieData: CategoryData[] =
    level === "transactions" ? [] :
    level === "categories"   ? (drillGroup?.categories ?? []) :
    view === "detail"        ? (categories.length > 0 ? categories : FALLBACK) :
                               (groups.length > 0 ? groups as CategoryData[] : FALLBACK);

  const total = pieData.reduce((s, d) => s + d.total, 0);

  // ── Navigation ──────────────────────────────────────────────────────────────

  async function drillToCategories(index: number) {
    if (view !== "groups" || level !== "groups") return;
    const g = groups[index];
    if (!g?.categories?.length) return;
    setDrillGroup(g);
    setLevel("categories");
    setActiveIndex(null);
  }

  async function drillToTransactions(cat: CategoryData) {
    if (level !== "categories") return;
    setDrillCat(cat);
    setLevel("transactions");
    setTxLoading(true);
    setTxs([]);

    // Fetch transactions de cette catégorie pour le mois courant
    // On cherche par nom de catégorie → d'abord trouver l'id
    try {
      const catsRes = await fetch(`${API_BASE}/categories/`);
      const allCats = await catsRes.json() as CategoryData[];
      const found = allCats.find((c) => c.name === cat.name);
      if (!found) { setTxLoading(false); return; }

      const params = new URLSearchParams({ month, category_id: String(found.id), limit: "20", exclude_transfers: "false" });
      const res = await fetch(`${API_BASE}/transactions/?${params}`);
      const data = await res.json();
      // Trier par montant décroissant
      const sorted = [...(data.items ?? [])].sort((a: TxItem, b: TxItem) => b.amount - a.amount);
      setTxs(sorted);
    } finally {
      setTxLoading(false);
    }
  }

  function goBack() {
    if (level === "transactions") {
      setLevel("categories");
      setDrillCat(null);
      setTxs([]);
    } else if (level === "categories") {
      setLevel("groups");
      setDrillGroup(null);
    }
    setActiveIndex(null);
  }

  function handleViewChange(v: "groups" | "detail") {
    setView(v);
    setLevel("groups");
    setDrillGroup(null);
    setDrillCat(null);
    setTxs([]);
    setActiveIndex(null);
  }

  // ── Breadcrumb ───────────────────────────────────────────────────────────────

  const breadcrumb = (
    <div className="flex items-center gap-1.5 min-w-0">
      {level !== "groups" && (
        <button onClick={goBack}
          className="text-slate-400 hover:text-white transition-colors text-base leading-none shrink-0">←</button>
      )}
      {level === "groups" && <h3 className="text-sm font-semibold text-white">Dépenses par catégorie</h3>}
      {level === "categories" && drillGroup && (
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: drillGroup.color }} />
          <span className="text-sm font-semibold text-white">{drillGroup.name}</span>
          <span className="text-xs text-slate-500">{fmt(drillGroup.total)}</span>
        </div>
      )}
      {level === "transactions" && drillGroup && drillCat && (
        <div className="flex items-center gap-1.5 min-w-0">
          <button onClick={() => { setLevel("categories"); setDrillCat(null); setTxs([]); }}
            className="text-xs text-slate-500 hover:text-slate-300 shrink-0">
            {drillGroup.name}
          </button>
          <span className="text-slate-600 shrink-0">›</span>
          <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: drillCat.color }} />
          <span className="text-sm font-semibold text-white truncate">{drillCat.name}</span>
          <span className="text-xs text-slate-500 shrink-0">{fmt(drillCat.total)}</span>
        </div>
      )}
    </div>
  );

  // ── Render ───────────────────────────────────────────────────────────────────
  if (!mounted) return <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-[400px]" />;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col gap-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        {breadcrumb}
        {level === "groups" && (
          <div className="flex text-[11px] rounded-lg overflow-hidden border border-slate-700 shrink-0">
            <button onClick={() => handleViewChange("groups")}
              className={`px-3 py-1 transition-colors ${view === "groups" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-slate-200"}`}>
              Groupes
            </button>
            <button onClick={() => handleViewChange("detail")}
              className={`px-3 py-1 transition-colors ${view === "detail" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-slate-200"}`}>
              Détail
            </button>
          </div>
        )}
      </div>

      {/* Niveau 1 & 2 : Pie + légende */}
      {level !== "transactions" && (
        <div className="flex items-center gap-4">
          <div className="shrink-0" style={{ width: 180, height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%" cy="50%"
                  innerRadius={50} outerRadius={80}
                  paddingAngle={2}
                  dataKey="total" nameKey="name"
                  onMouseEnter={(_, i) => setActiveIndex(i)}
                  onMouseLeave={() => setActiveIndex(null)}
                  onClick={(_, i) => level === "groups" ? drillToCategories(i) : undefined}
                  style={{ cursor: level === "groups" && view === "groups" ? "pointer" : "default" }}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color}
                      opacity={activeIndex === null || activeIndex === i ? 1 : 0.45} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v) => [fmt(Number(v)), ""]}
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#94a3b8" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="flex-1 min-w-0 max-h-48 overflow-y-auto pr-1 space-y-1.5">
            {pieData.map((entry, i) => {
              const sharePct   = total > 0 ? Math.round(entry.total / total * 100) : 0;
              const clickable  = level === "groups" && view === "groups";
              const catClickable = level === "categories";
              const group       = level === "groups" ? groups[i] : null;
              const overLimit   = group?.over_limit;
              const limit       = group?.budget_monthly ?? null;  // budget mensuel = annuel / 12
              const limitPct    = limit ? Math.round(entry.total / limit * 100) : null;
              const limitPctCapped = limitPct !== null ? Math.min(limitPct, 100) : null;
              // Quand budget configuré : afficher % du budget ; sinon % des dépenses totales
              const displayPct  = limitPct !== null ? limitPct : sharePct;
              const displayPctColor = limitPct !== null
                ? (overLimit ? "text-red-400 font-bold" : limitPct > 90 ? "text-amber-400 font-medium" : "text-emerald-400")
                : "text-slate-500";

              return (
                <button key={i}
                  onClick={() => {
                    if (clickable) drillToCategories(i);
                    else if (catClickable) drillToTransactions(entry);
                  }}
                  onMouseEnter={() => setActiveIndex(i)}
                  onMouseLeave={() => setActiveIndex(null)}
                  className={`w-full text-left rounded-lg px-2 py-1.5 transition-colors
                    ${(clickable || catClickable) ? "hover:bg-slate-800 cursor-pointer" : "cursor-default"}
                    ${activeIndex === i ? "bg-slate-800" : ""}
                    ${overLimit ? "ring-1 ring-red-500/30" : ""}
                  `}
                >
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: entry.color }} />
                    <span className="text-xs text-slate-300 truncate flex-1">{entry.name}</span>
                    {overLimit && <span className="text-[10px] text-red-400 shrink-0">⚠</span>}
                    {(clickable || catClickable) && !overLimit && <span className="text-[9px] text-slate-600 shrink-0">▶</span>}
                    <span className={`text-xs tabular-nums shrink-0 ${displayPctColor}`} title={limitPct !== null ? "% du budget mensuel" : "% des dépenses totales"}>
                      {displayPct}%
                    </span>
                    <span className={`text-xs tabular-nums w-20 text-right shrink-0 ${overLimit ? "text-red-400 font-medium" : "text-slate-400"}`}>
                      {fmt(entry.total)}
                    </span>
                  </div>
                  {/* Barre de progression mensuelle (budget annuel / 12) */}
                  {limit && limitPctCapped !== null && (
                    <>
                      <div className="mt-1 h-1 rounded-full bg-slate-700 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${overLimit ? "bg-red-500" : limitPctCapped > 90 ? "bg-amber-400" : "bg-emerald-500"}`}
                          style={{ width: `${limitPctCapped}%` }}
                        />
                      </div>
                      <div className="flex justify-between mt-0.5">
                        <span className={`text-[9px] ${overLimit ? "text-red-400" : "text-slate-600"}`}>
                          {overLimit ? `+${fmt(entry.total - limit)} dépassé` : `${fmt(limit - entry.total)} restant`}
                        </span>
                        <span className="text-[9px] text-slate-600">{fmt(limit)}/mois</span>
                      </div>
                    </>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Niveau 3 : liste de transactions */}
      {level === "transactions" && (
        <div className="space-y-1">
          {txLoading && (
            <p className="text-xs text-slate-500 text-center py-4">Chargement…</p>
          )}
          {!txLoading && txs.length === 0 && (
            <p className="text-xs text-slate-600 text-center py-4">Aucune transaction ce mois</p>
          )}
          {!txLoading && txs.map((tx, i) => (
            <div key={tx.id}
              className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-xs text-slate-600 tabular-nums shrink-0 w-4 text-right">{i + 1}.</span>
                <span className="text-xs text-slate-500 shrink-0">{tx.date}</span>
                <span className="text-xs text-slate-300 truncate">{tx.label}</span>
              </div>
              <span className="text-xs font-medium text-slate-200 tabular-nums shrink-0 ml-3">
                {fmtFull(tx.amount)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Hints */}
      {level === "groups" && view === "groups" && groups.length > 0 && (
        <p className="text-[10px] text-slate-600 text-center -mt-1">Cliquez sur un groupe pour voir ses catégories</p>
      )}
      {level === "categories" && (
        <p className="text-[10px] text-slate-600 text-center -mt-1">Cliquez sur une catégorie pour voir les transactions</p>
      )}
    </div>
  );
}
