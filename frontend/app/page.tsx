"use client";
import { useState, useEffect } from "react";
import { Wallet, TrendingUp, TrendingDown, PiggyBank, Percent } from "lucide-react";
import StatCard from "@/components/ui/StatCard";
import ExpensesByCategory from "@/components/charts/ExpensesByCategory";
import MonthlyEvolution from "@/components/charts/MonthlyEvolution";
import RollingBudget from "@/components/charts/RollingBudget";
import CurrentMonthMonitor from "@/components/charts/CurrentMonthMonitor";

import { API_BASE } from "@/lib/config";

const fmt = (v: number) =>
  v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

const fmtMonth = (m: string) => {
  const [y, mo] = m.split("-");
  return new Date(Number(y), Number(mo) - 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
};

interface CategoryData { name: string; color: string; total: number }
interface GroupData {
  name: string;
  color: string;
  total: number;
  categories: CategoryData[];
  budget_annual?: number | null;
  budget_monthly: number | null;
  over_limit: boolean;
  projection_mode: "linear" | "fixed_historical" | "actual_only";
  projection_amount: number;
  projection_over_limit: boolean;
  projection_source: string;
  projection_reference: number | null;
}
interface Top10Item   { label: string; amount: number; category: string; category_color: string }
interface MonthPoint  { month: string; label: string; revenus: number; depenses: number; epargne: number }
interface TxItem      { id: number; date: string; label: string; amount: number; type: string; category_name: string | null; bank: string | null; account_name: string | null; is_internal_transfer: boolean; is_investment: boolean; is_neutral: boolean; is_compte_pro: boolean }

interface MonthlySummary {
  month: string;
  revenus: number;
  depenses: number;
  investissements: number;
  epargne: number;
  taux_epargne: number;
  categories: CategoryData[];
  groups: GroupData[];
  virements_internes: number;
  virements_envoyes: number;
  virements_recus: number;
  nb_transactions: number;
  top10: Top10Item[];
  is_current_month: boolean;
  days_elapsed: number | null;
  days_in_month: number | null;
  pace_factor: number | null;
}

export default function DashboardPage() {
  const [months, setMonths]     = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [summary, setSummary]   = useState<MonthlySummary | null>(null);
  const [history, setHistory]   = useState<MonthPoint[]>([]);
  const [loading, setLoading]   = useState(false);
  const [panel, setPanel]           = useState<{ title: string; txType: "credit" | "debit" } | null>(null);
  const [panelTxs, setPanelTxs]     = useState<TxItem[]>([]);
  const [panelDeductions, setPanelDeductions] = useState<TxItem[]>([]);
  const [panelRefunds, setPanelRefunds]       = useState<TxItem[]>([]);
  const [panelNeutral, setPanelNeutral]       = useState<TxItem[]>([]);
  const [panelLoading, setPanelLoading] = useState(false);

  // Load available months on mount
  useEffect(() => {
    fetch(`${API_BASE}/patrimony/months`)
      .then(r => r.json())
      .then((data: string[]) => {
        setMonths(data);
        if (data.length > 0) {
          const prev = new Date();
          prev.setDate(1);
          prev.setMonth(prev.getMonth() - 1);
          const prevStr = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, "0")}`;
          setSelected(data.includes(prevStr) ? prevStr : data[0]);
        }
      })
      .catch(() => {});

    // 12-month history (independent of selected month)
    fetch(`${API_BASE}/transactions/summary/history?months=12`)
      .then(r => r.json())
      .then(setHistory)
      .catch(() => {});
  }, []);

  // Load monthly summary when selected month changes
  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    fetch(`${API_BASE}/transactions/summary/monthly?month=${selected}`)
      .then(r => r.json())
      .then((data: MonthlySummary) => { setSummary(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [selected]);

  const hasTx = summary && summary.nb_transactions > 0;

  async function openPanel(title: string, txType: "credit" | "debit") {
    setPanel({ title, txType });
    setPanelLoading(true);
    setPanelTxs([]);
    setPanelDeductions([]);
    setPanelRefunds([]);
    setPanelNeutral([]);

    const INCOME_CATS = ["Revenus"];

    // Fetch all transactions (including internal) pour revenus
    const params = new URLSearchParams({ month: selected, limit: "500", exclude_transfers: txType === "debit" ? "true" : "false" });
    const data = await fetch(`${API_BASE}/transactions/?${params}`).then(r => r.json());
    const items = data.items as TxItem[];

    if (txType === "credit") {
      // Revenus réels uniquement = crédits sans catégorie ou catégorie "Revenus", hors neutres
      const revenues = items
        .filter(t => t.type === "credit" && !t.is_internal_transfer && !t.is_neutral &&
          (t.category_name === null || INCOME_CATS.includes(t.category_name)))
        .sort((a, b) => b.amount - a.amount);
      // Apports compte pro = débits flagués is_compte_pro (déduits des revenus)
      const deductions = items
        .filter(t => t.type === "debit" && t.is_compte_pro)
        .sort((a, b) => b.amount - a.amount);
      // Flux neutres (crédits) = non comptabilisés, affichés pour info
      const neutral = items
        .filter(t => t.type === "credit" && t.is_neutral)
        .sort((a, b) => b.amount - a.amount);
      setPanelTxs(revenues);
      setPanelDeductions(deductions);
      setPanelRefunds([]);
      setPanelNeutral(neutral);
    } else {
      // Panel dépenses : fetch sans filtre exclude_transfers pour avoir aussi les crédits remboursements
      const allParams = new URLSearchParams({ month: selected, limit: "500", exclude_transfers: "false" });
      const allData = await fetch(`${API_BASE}/transactions/?${allParams}`).then(r => r.json());
      const allItems = allData.items as TxItem[];

      const debits = allItems.filter(t => t.type === "debit" && !t.is_internal_transfer && !t.is_compte_pro);
      const counted = debits.filter(t => !t.is_investment && !t.is_neutral).sort((a, b) => b.amount - a.amount);
      const ignored = debits.filter(t => t.is_investment || t.is_neutral).sort((a, b) => b.amount - a.amount);
      // Remboursements = crédits avec catégorie dépense → réduisent les dépenses
      const refunds = allItems
        .filter(t => t.type === "credit" && !t.is_internal_transfer &&
          t.category_name !== null && !INCOME_CATS.includes(t.category_name))
        .sort((a, b) => b.amount - a.amount);
      setPanelTxs(counted);
      setPanelDeductions(ignored);
      setPanelRefunds(refunds);
    }
    setPanelLoading(false);
  }

  const fmtFull = (v: number) => v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard Budget</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {selected ? fmtMonth(selected) : "—"}
            {summary && ` — ${summary.nb_transactions} transactions`}
          </p>
        </div>
        <select
          value={selected}
          onChange={e => setSelected(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none"
        >
          {months.map(m => (
            <option key={m} value={m}>{fmtMonth(m)}</option>
          ))}
        </select>
      </div>

      {/* KPI Cards */}
      <div className={`grid grid-cols-2 gap-4 ${hasTx && (summary?.investissements ?? 0) > 0 ? "lg:grid-cols-6" : "lg:grid-cols-5"}`}>
        <StatCard
          label="Revenus nets"
          value={hasTx ? fmt(summary!.revenus) : "—"}
          icon={Wallet}
          color="indigo"
          trend={0}
          index={0}
          onClick={hasTx ? () => openPanel("Revenus", "credit") : undefined}
        />
        <StatCard
          label="Dépenses totales"
          value={hasTx ? fmt(summary!.depenses) : "—"}
          icon={TrendingDown}
          color="red"
          trend={0}
          index={1}
          onClick={hasTx ? () => openPanel("Dépenses", "debit") : undefined}
        />
        <StatCard
          label="Épargne"
          value={hasTx ? fmt(summary!.epargne) : "—"}
          icon={PiggyBank}
          color="green"
          trend={0}
          index={2}
        />
        {hasTx && (summary?.investissements ?? 0) > 0 && (
          <StatCard
            label="Investissements"
            value={fmt(summary!.investissements)}
            icon={TrendingUp}
            color="indigo"
            trend={0}
            index={2}
          />
        )}
        <StatCard
          label="Taux d'épargne"
          value={hasTx ? `${summary!.taux_epargne} %` : "—"}
          icon={Percent}
          color="amber"
          index={3}
        />
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <p className="text-xs text-slate-400 mb-3">Virements internes</p>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Envoyés</span>
              <span className="text-sm font-semibold text-red-400">
                {hasTx ? `−${fmt(summary!.virements_envoyes)}` : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Reçus</span>
              <span className="text-sm font-semibold text-emerald-400">
                {hasTx ? `+${fmt(summary!.virements_recus)}` : "—"}
              </span>
            </div>
            <div className="border-t border-slate-700 pt-2 flex items-center justify-between">
              <span className="text-xs text-slate-400">Net</span>
              <span className="text-sm font-bold text-white">
                {hasTx ? fmt(summary!.virements_recus - summary!.virements_envoyes) : "—"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {loading && (
        <p className="text-center text-slate-500 text-sm py-4">Chargement...</p>
      )}

      {/* Charts */}
      {!loading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ExpensesByCategory groups={summary?.groups.filter((g) => g.total > 0) ?? []} categories={summary?.categories ?? []} month={selected} />
          <MonthlyEvolution history={history} />
        </div>
      )}

      {/* Monitoring mois en cours */}
      {!loading && summary?.is_current_month && summary.pace_factor && summary.days_elapsed && summary.days_in_month && (
        <CurrentMonthMonitor
          groups={summary.groups}
          depenses={summary.depenses}
          days_elapsed={summary.days_elapsed}
          days_in_month={summary.days_in_month}
        />
      )}

      {/* Suivi annuel glissant */}
      {!loading && <RollingBudget pivotMonth={selected} />}

      {/* Top 10 */}
      {!loading && summary && summary.top10.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Top 10 des dépenses</h3>
          <div className="space-y-2">
            {summary.top10.map((item, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-slate-800/60 last:border-0">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 w-4">{i + 1}</span>
                  <div>
                    <p className="text-sm text-slate-200">{item.label}</p>
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                      style={{ backgroundColor: `${item.category_color}25`, color: item.category_color }}
                    >
                      {item.category}
                    </span>
                  </div>
                </div>
                <span className="text-sm font-semibold text-white">{fmt(item.amount)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && summary && summary.nb_transactions === 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center">
          <p className="text-slate-400 text-sm">Aucune transaction importée pour ce mois.</p>
          <p className="text-slate-600 text-xs mt-1">Importez un relevé CSV depuis la page Import.</p>
        </div>
      )}

      {/* Panel latéral transactions */}
      {panel && (
        <>
          {/* Overlay */}
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setPanel(null)}
          />
          {/* Drawer */}
          <div className="fixed right-0 top-0 h-full w-[420px] bg-slate-950 border-l border-slate-800 z-50 flex flex-col shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
              <div>
                <h2 className="text-sm font-semibold text-white">{panel.title}</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {fmtMonth(selected)} — {panelTxs.length} transaction(s)
                  {panel.txType === "debit" && panelRefunds.length > 0 && ` · ${panelRefunds.length} remboursement(s)`}
                  {panel.txType === "debit" && panelDeductions.length > 0 && ` · ${panelDeductions.length} ignorée(s)`}
                </p>
              </div>
              <button
                onClick={() => setPanel(null)}
                className="text-slate-500 hover:text-white transition-colors text-lg leading-none"
              >✕</button>
            </div>

            {/* Liste */}
            <div className="flex-1 overflow-y-auto">
              {panelLoading && (
                <p className="text-xs text-slate-500 text-center py-8">Chargement…</p>
              )}
              {!panelLoading && panelTxs.length === 0 && panelDeductions.length === 0 && panelRefunds.length === 0 && (
                <p className="text-xs text-slate-600 text-center py-8">Aucune transaction</p>
              )}

              {/* Revenus */}
              {!panelLoading && panelTxs.map((tx, i) => (
                <div key={tx.id} className="flex items-center justify-between px-5 py-3 border-b border-slate-800/60 hover:bg-slate-900 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs text-slate-600 w-5 text-right shrink-0">{i + 1}.</span>
                    <div className="min-w-0">
                      <p className="text-xs text-slate-300 truncate">{tx.label}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-slate-600">{tx.date}</span>
                        {tx.category_name && <span className="text-[10px] text-slate-500">{tx.category_name}</span>}
                        {tx.account_name && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400">{tx.account_name}</span>}
                      </div>
                    </div>
                  </div>
                  <span className={`text-xs font-medium tabular-nums shrink-0 ml-3 ${panel.txType === "credit" ? "text-emerald-400" : "text-slate-300"}`}>
                    {panel.txType === "credit" ? "+" : "−"}{fmtFull(tx.amount)}
                  </span>
                </div>
              ))}

              {/* Déductions Compte pro (panel revenus) / Non comptabilisées (panel dépenses) */}
              {!panelLoading && panelDeductions.length > 0 && (
                <>
                  {panel.txType === "credit" ? (
                    <div className="px-5 py-2 border-y bg-orange-500/5 border-orange-500/20">
                      <p className="text-[10px] text-orange-400 font-medium uppercase tracking-wider">Apports Compte pro</p>
                      <p className="text-[10px] text-slate-600 mt-0.5">Virements internes catégorisés &quot;Compte pro&quot; — déduits des revenus car argent déjà dans le foyer</p>
                    </div>
                  ) : (
                    <div className="px-5 py-2 border-y bg-slate-800/50 border-slate-700">
                      <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Non comptabilisées (investissement / neutre)</span>
                    </div>
                  )}
                  {panelDeductions.map((tx) => (
                    <div key={tx.id} className="flex items-center justify-between px-5 py-3 border-b border-slate-800/60 hover:bg-slate-900/50 transition-colors opacity-50">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="text-xs text-slate-600 w-5 text-right shrink-0">{panel.txType === "credit" ? "↩" : "∅"}</span>
                        <div className="min-w-0">
                          <p className="text-xs text-slate-500 truncate">{tx.label}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-slate-600">{tx.date}</span>
                            {tx.is_investment && <span className="text-[9px] text-emerald-600">investissement</span>}
                            {tx.is_neutral && <span className="text-[9px] text-slate-600">neutre</span>}
                            {tx.account_name && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400">{tx.account_name}</span>}
                          </div>
                        </div>
                      </div>
                      <span className={`text-xs tabular-nums shrink-0 ml-3 ${panel.txType === "credit" ? "text-orange-400" : "text-slate-600"}`}>
                        −{fmtFull(tx.amount)}
                      </span>
                    </div>
                  ))}
                </>
              )}

              {/* Flux neutres (non comptabilisés) */}
              {!panelLoading && panelNeutral.length > 0 && (
                <>
                  <div className="px-5 py-2 border-y bg-slate-800/50 border-slate-700">
                    <p className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Flux neutres — non comptabilisés</p>
                    <p className="text-[10px] text-slate-600 mt-0.5">Créances, remboursements de prêt... exclus des revenus</p>
                  </div>
                  {panelNeutral.map((tx) => (
                    <div key={tx.id} className="flex items-center justify-between px-5 py-3 border-b border-slate-800/60 opacity-50">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="text-xs text-slate-600 w-5 text-right shrink-0">∅</span>
                        <div className="min-w-0">
                          <p className="text-xs text-slate-500 truncate">{tx.label}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-slate-600">{tx.date}</span>
                            {tx.account_name && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400">{tx.account_name}</span>}
                          </div>
                        </div>
                      </div>
                      <span className="text-xs tabular-nums shrink-0 ml-3 text-slate-600">
                        +{fmtFull(tx.amount)}
                      </span>
                    </div>
                  ))}
                </>
              )}

              {/* Remboursements (crédits catégorie dépense) */}
              {!panelLoading && panelRefunds.length > 0 && (
                <>
                  <div className="px-5 py-2 bg-amber-500/5 border-y border-amber-500/20">
                    <span className="text-[10px] text-amber-400 font-medium uppercase tracking-wider">Remboursements (déduits des dépenses)</span>
                  </div>
                  {panelRefunds.map((tx) => (
                    <div key={tx.id} className="flex items-center justify-between px-5 py-3 border-b border-slate-800/60 hover:bg-slate-900 transition-colors">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="text-xs text-amber-500/50 w-5 text-right shrink-0">↩</span>
                        <div className="min-w-0">
                          <p className="text-xs text-slate-400 truncate">{tx.label}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-slate-600">{tx.date}</span>
                            {tx.category_name && <span className="text-[10px] text-slate-500">{tx.category_name}</span>}
                            {tx.account_name && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400">{tx.account_name}</span>}
                          </div>
                        </div>
                      </div>
                      <span className="text-xs font-medium tabular-nums shrink-0 ml-3 text-amber-400">
                        +{fmtFull(tx.amount)}
                      </span>
                    </div>
                  ))}
                </>
              )}
            </div>

            {/* Total */}
            {!panelLoading && (panelTxs.length > 0 || panelDeductions.length > 0 || panelRefunds.length > 0) && (
              <div className="px-5 py-4 border-t border-slate-800 space-y-1">
                {panel.txType === "credit" && (panelDeductions.length > 0 || panelRefunds.length > 0) && (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-500">Revenus bruts</span>
                      <span className="text-xs text-slate-400 tabular-nums">
                        +{fmtFull(panelTxs.reduce((s, t) => s + t.amount, 0))}
                      </span>
                    </div>
                    {panelDeductions.length > 0 && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-500">Apports Compte pro</span>
                        <span className="text-xs text-orange-400 tabular-nums">
                          −{fmtFull(panelDeductions.reduce((s, t) => s + t.amount, 0))}
                        </span>
                      </div>
                    )}
                    <div className="border-t border-slate-700 pt-1 flex items-center justify-between">
                      <span className="text-xs text-slate-400 font-medium">Revenus nets</span>
                      <span className="text-sm font-bold text-emerald-400 tabular-nums">
                        {fmtFull(panelTxs.reduce((s, t) => s + t.amount, 0) - panelDeductions.reduce((s, t) => s + t.amount, 0))}
                      </span>
                    </div>
                  </>
                )}
                {(panel.txType === "debit" || (panelDeductions.length === 0 && panelRefunds.length === 0)) && (
                  <>
                    {panel.txType === "debit" && panelRefunds.length > 0 && (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-500">Dépenses brutes</span>
                          <span className="text-xs text-slate-400 tabular-nums">
                            {fmtFull(panelTxs.reduce((s, t) => s + t.amount, 0))}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-500">Remboursements</span>
                          <span className="text-xs text-emerald-500 tabular-nums">
                            −{fmtFull(panelRefunds.reduce((s, t) => s + t.amount, 0))}
                          </span>
                        </div>
                      </>
                    )}
                    {panel.txType === "debit" && panelDeductions.length > 0 && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-500">Non comptabilisées</span>
                        <span className="text-xs text-slate-600 tabular-nums">
                          −{fmtFull(panelDeductions.reduce((s, t) => s + t.amount, 0))}
                        </span>
                      </div>
                    )}
                    <div className={`flex items-center justify-between ${panelRefunds.length > 0 && panel.txType === "debit" ? "border-t border-slate-700 pt-1" : ""}`}>
                      <span className="text-xs text-slate-400 font-medium">
                        {panel.txType === "debit" && panelRefunds.length > 0 ? "Dépenses nettes" : "Total comptabilisé"}
                      </span>
                      <span className="text-sm font-bold tabular-nums text-white">
                        {fmtFull(panelTxs.reduce((s, t) => s + t.amount, 0) - panelRefunds.reduce((s, t) => s + t.amount, 0))}
                      </span>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
