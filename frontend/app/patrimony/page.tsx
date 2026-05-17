"use client";
import { useState, useEffect } from "react";
import { CheckCircle2, Plus, Save } from "lucide-react";
import PatrimonyChart from "@/components/charts/PatrimonyChart";
import AssetsBreakdown from "@/components/charts/AssetsBreakdown";
import LiquidityAnalysis from "@/components/charts/LiquidityAnalysis";

import { API_BASE } from "@/lib/config";

const fmt = (v: number) =>
  v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

const fmtMonth = (m: string) => {
  const [y, mo] = m.split("-");
  return new Date(Number(y), Number(mo) - 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
};

interface AssetGroup { name: string; value: number; color: string }
interface AccountSnap {
  account_id: number;
  account_name: string;
  account_type: string;
  bank: string;
  members: string[];
  value: number | null;
}
interface Snapshot {
  month: string;
  accounts: AccountSnap[];
  totals: { actifs: number; passifs: number; patrimoine_net: number };
}
interface MonthPoint { month: string; label: string; actifs: number; passifs: number; net: number }
interface NetEvolution {
  mode: string;
  series: { key: string; name: string; color: string }[];
  points: Record<string, string | number>[];
}
interface Indicators {
  epargne_securite: number; epargne_dispo: number;
  capital_investi: number; investi_plus_livrets: number;
  patrimoine_hors_rp: number; patrimoine_net: number;
  layers: { key: string; label: string; value: number; color: string }[];
}
interface DraftItem {
  account_id: number;
  account_name: string;
  account_type: string;
  bank: string | null;
  members: string[];
  value: number | null;
  note: string | null;
  source_month: string | null;
  source_value: number | null;
}
interface DraftGroup {
  type: string;
  label: string;
  items: DraftItem[];
}
interface DraftPayload {
  month: string;
  groups: DraftGroup[];
  totals: { actifs: number; passifs: number; patrimoine_net: number };
}

const nextMonth = (month: string) => {
  if (!month) return new Date().toISOString().slice(0, 7);
  const [year, mo] = month.split("-").map(Number);
  const date = new Date(year, mo, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Erreur ${res.status}`);
  }
  return res.json();
}

export default function PatrimonyPage() {
  const [months, setMonths]           = useState<string[]>([]);
  const [selected, setSelected]       = useState("");
  const [snapshot, setSnapshot]       = useState<Snapshot | null>(null);
  const [actifs, setActifs]           = useState<AssetGroup[]>([]);
  const [history, setHistory]         = useState<MonthPoint[]>([]);
  const [netHistory, setNetHistory]   = useState<NetEvolution | null>(null);
  const [liqHistory, setLiqHistory]       = useState<NetEvolution | null>(null);
  const [metricsHistory, setMetricsHistory] = useState<NetEvolution | null>(null);
  const [indicators, setIndicators]   = useState<Indicators | null>(null);
  const [loading, setLoading]         = useState(false);
  const [netMode, setNetMode]         = useState(false);
  const [chartMode, setChartMode]     = useState<"brut" | "net" | "liquidity" | "metrics">("brut");
  const [draftOpen, setDraftOpen]     = useState(false);
  const [draftMonth, setDraftMonth]   = useState("");
  const [draft, setDraft]             = useState<DraftPayload | null>(null);
  const [activeDraftType, setActiveDraftType] = useState("");
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/patrimony/months`)
      .then(r => r.json())
      .then((data: string[]) => {
        setMonths(data);
        if (data.length > 0) setSelected(data[0]);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!draftMonth && months.length > 0) setDraftMonth(nextMonth(months[0]));
  }, [months, draftMonth]);

  // Recharge snapshot + évolution au changement de mois
  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/patrimony/snapshot?month=${selected}`).then(r => r.json()),
      fetch(`${API_BASE}/patrimony/evolution?up_to=${selected}&mode=brut`).then(r => r.json()),
      fetch(`${API_BASE}/patrimony/evolution?up_to=${selected}&mode=net`).then(r => r.json()),
      fetch(`${API_BASE}/patrimony/evolution?up_to=${selected}&mode=liquidity`).then(r => r.json()),
      fetch(`${API_BASE}/patrimony/evolution?up_to=${selected}&mode=metrics`).then(r => r.json()),
      fetch(`${API_BASE}/patrimony/indicators?month=${selected}`).then(r => r.json()),
    ])
      .then(([snap, evo, netEvo, liqEvo, metricsEvo, ind]) => {
        setSnapshot(snap);
        setHistory(evo);
        setNetHistory(netEvo);
        setLiqHistory(liqEvo);
        setMetricsHistory(metricsEvo);
        setIndicators(ind);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selected]);

  // Recharge breakdown au changement de mois OU de mode brut/net
  useEffect(() => {
    if (!selected) return;
    fetch(`${API_BASE}/patrimony/breakdown?month=${selected}&net=${netMode}`)
      .then(r => r.json())
      .then(setActifs)
      .catch(() => {});
  }, [selected, netMode]);

  const totals = snapshot?.totals;
  const tauxEndettement = totals && totals.actifs > 0
    ? ((totals.passifs / totals.actifs) * 100).toFixed(1)
    : "—";
  const activeDraftGroup = draft?.groups.find(g => g.type === activeDraftType) ?? draft?.groups[0] ?? null;

  const reloadMonths = async (monthToSelect?: string) => {
    const data = await fetch(`${API_BASE}/patrimony/months`, { cache: "no-store" }).then(r => r.json());
    setMonths(data);
    if (monthToSelect) setSelected(monthToSelect);
  };

  const startDraft = async () => {
    if (!draftMonth) return;
    setDraftLoading(true);
    setDraftMessage("");
    try {
      const data = await requestJson<DraftPayload>("/patrimony/draft", {
        method: "POST",
        body: JSON.stringify({ month: draftMonth }),
      });
      setDraft(data);
      setActiveDraftType(data.groups[0]?.type ?? "");
      setDraftOpen(true);
    } catch (err) {
      setDraftMessage(err instanceof Error ? err.message : "Impossible de préparer le brouillon.");
    } finally {
      setDraftLoading(false);
    }
  };

  const updateDraftValue = (accountId: number, value: string) => {
    setDraft(current => {
      if (!current) return current;
      const parsed = value === "" ? null : Number(value);
      const groups = current.groups.map(group => ({
        ...group,
        items: group.items.map(item =>
          item.account_id === accountId
            ? { ...item, value: parsed === null || Number.isFinite(parsed) ? parsed : item.value }
            : item
        ),
      }));
      const values = groups.flatMap(group => group.items.map(item => item.value)).filter(v => v !== null);
      const actifs = values.reduce((sum, v) => sum + (v > 0 ? v : 0), 0);
      const passifs = values.reduce((sum, v) => sum + (v < 0 ? Math.abs(v) : 0), 0);
      return {
        ...current,
        groups,
        totals: {
          actifs,
          passifs,
          patrimoine_net: actifs - passifs,
        },
      };
    });
  };

  const persistDraft = async () => {
    if (!draft) return;
    const items = draft.groups.flatMap(group =>
      group.items.map(item => ({ account_id: item.account_id, value: item.value, note: item.note }))
    );
    return requestJson<DraftPayload>("/patrimony/draft", {
      method: "PUT",
      body: JSON.stringify({ month: draft.month, items }),
    });
  };

  const saveDraft = async () => {
    if (!draft) return;
    setDraftLoading(true);
    setDraftMessage("");
    try {
      const data = await persistDraft();
      if (!data) return;
      setDraft(data);
      setDraftMessage("Brouillon sauvegardé.");
    } catch (err) {
      setDraftMessage(err instanceof Error ? err.message : "Impossible de sauvegarder.");
    } finally {
      setDraftLoading(false);
    }
  };

  const publishDraft = async () => {
    if (!draft) return;
    setDraftLoading(true);
    setDraftMessage("");
    try {
      const saved = await persistDraft();
      if (!saved) return;
      await requestJson<{ ok: boolean; month: string }>("/patrimony/draft/publish", {
        method: "POST",
        body: JSON.stringify({ month: saved.month }),
      });
      await reloadMonths(saved.month);
      setDraft(null);
      setDraftOpen(false);
      setDraftMessage("Mois validé et publié.");
    } catch (err) {
      setDraftMessage(err instanceof Error ? err.message : "Impossible de valider le mois.");
    } finally {
      setDraftLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Patrimoine</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {selected ? fmtMonth(selected) : "—"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selected}
            onChange={e => setSelected(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none"
          >
            {months.map(m => (
              <option key={m} value={m}>{fmtMonth(m)}</option>
            ))}
          </select>
          <button
            onClick={() => setDraftOpen(open => !open)}
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg px-3 py-2 transition-colors"
          >
            <Plus size={16} />
            Saisir mois
          </button>
        </div>
      </div>

      {draftOpen && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-white">Saisie mensuelle</h2>
              <p className="text-xs text-slate-500 mt-1">
                Brouillon privé jusqu&apos;à validation. Préremplissage depuis le dernier mois publié.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="month"
                value={draftMonth}
                onChange={e => setDraftMonth(e.target.value)}
                className="bg-slate-950 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 outline-none"
              />
              <button
                onClick={startDraft}
                disabled={draftLoading || !draftMonth}
                className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-100 text-sm font-medium rounded-lg px-3 py-2 transition-colors"
              >
                <Plus size={16} />
                Préparer
              </button>
              <button
                onClick={saveDraft}
                disabled={draftLoading || !draft}
                className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-100 text-sm font-medium rounded-lg px-3 py-2 transition-colors"
              >
                <Save size={16} />
                Sauver
              </button>
              <button
                onClick={publishDraft}
                disabled={draftLoading || !draft}
                className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-3 py-2 transition-colors"
              >
                <CheckCircle2 size={16} />
                Valider
              </button>
            </div>
          </div>

          {draftMessage && (
            <p className="text-xs text-slate-400">{draftMessage}</p>
          )}

          {draft && (
            <>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Actifs", value: draft.totals.actifs, color: "text-emerald-400" },
                  { label: "Passifs", value: draft.totals.passifs, color: "text-red-400" },
                  { label: "Net draft", value: draft.totals.patrimoine_net, color: "text-indigo-400" },
                ].map(item => (
                  <div key={item.label} className="bg-slate-950 border border-slate-800 rounded-lg p-3">
                    <p className="text-[11px] text-slate-500">{item.label}</p>
                    <p className={`text-base font-semibold ${item.color}`}>{fmt(item.value)}</p>
                  </div>
                ))}
              </div>

              <div className="flex gap-2 overflow-x-auto pb-1">
                {draft.groups.map(group => (
                  <button
                    key={group.type}
                    onClick={() => setActiveDraftType(group.type)}
                    className={`whitespace-nowrap rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                      activeDraftType === group.type
                        ? "border-indigo-500 bg-indigo-500/15 text-indigo-200"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {group.label}
                  </button>
                ))}
              </div>

              {activeDraftGroup && (
                <div className="overflow-hidden rounded-lg border border-slate-800">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-950 text-xs uppercase tracking-wider text-slate-500">
                      <tr>
                        <th className="px-4 py-3 text-left">Compte</th>
                        <th className="px-4 py-3 text-left">Source</th>
                        <th className="px-4 py-3 text-right">Valeur</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeDraftGroup.items.map(item => (
                        <tr key={item.account_id} className="border-t border-slate-800">
                          <td className="px-4 py-3">
                            <p className="font-medium text-slate-200">{item.account_name}</p>
                            <p className="text-xs text-slate-500">
                              {[item.bank, item.members.join(", ")].filter(Boolean).join(" · ") || "—"}
                            </p>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-500">
                            {item.source_month ? `${fmtMonth(item.source_month)} · ${item.source_value == null ? "—" : fmt(item.source_value)}` : "Solde initial"}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <input
                              type="number"
                              step="0.01"
                              value={item.value ?? ""}
                              onChange={e => updateDraftValue(item.account_id, e.target.value)}
                              className="w-36 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-right text-sm text-white outline-none focus:border-indigo-500"
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Actifs bruts",       value: totals ? fmt(totals.actifs)        : "—", color: "text-emerald-400" },
          { label: "Passifs",            value: totals ? fmt(totals.passifs)        : "—", color: "text-red-400" },
          { label: "Patrimoine net",     value: totals ? fmt(totals.patrimoine_net) : "—", color: "text-indigo-400" },
          { label: "Taux d'endettement", value: totals ? `${tauxEndettement} %`     : "—", color: "text-amber-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <p className="text-xs text-slate-400 mb-2">{label}</p>
            <p className={`text-xl font-bold ${color}`}>
              {loading ? <span className="text-slate-600">…</span> : value}
            </p>
          </div>
        ))}
      </div>

      {/* Analyse patrimoniale */}
      {!loading && <LiquidityAnalysis indicators={indicators} accounts={snapshot?.accounts ?? []} />}

      {/* Courbe évolution */}
      <PatrimonyChart
        history={history}
        netHistory={netHistory}
        liqHistory={liqHistory}
        metricsHistory={metricsHistory}
        mode={chartMode}
        onModeChange={setChartMode}
      />

      {/* Répartition + Détail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Camembert avec toggle Brut / Net */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Répartition des actifs</h3>
            <div className="flex rounded-lg overflow-hidden border border-slate-700 text-xs">
              <button
                onClick={() => setNetMode(false)}
                className={`px-3 py-1.5 transition-colors ${!netMode ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"}`}
              >
                Brut
              </button>
              <button
                onClick={() => setNetMode(true)}
                className={`px-3 py-1.5 transition-colors ${netMode ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"}`}
              >
                Net
              </button>
            </div>
          </div>
          <AssetsBreakdown actifs={actifs} />
        </div>

        {/* Détail texte */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Détail</h3>
            {netMode && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-400 font-medium">
                Vue nette — immo déduit du prêt
              </span>
            )}
          </div>
          {loading ? (
            <p className="text-slate-600 text-sm">Chargement…</p>
          ) : (
            <div className="space-y-3">
              {actifs.map((a) => {
                const total = actifs.reduce((s, x) => s + x.value, 0);
                return (
                  <div key={a.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: a.color }} />
                      <span className="text-sm text-slate-300">{a.name}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-medium text-white">{fmt(a.value)}</span>
                      <span className="text-xs text-slate-500 ml-2">
                        {total > 0 ? ((a.value / total) * 100).toFixed(1) : 0}%
                      </span>
                    </div>
                  </div>
                );
              })}
              {!netMode && totals && totals.passifs > 0 && (
                <div className="border-t border-slate-700 pt-2 mt-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />
                      <span className="text-sm text-slate-300">Passifs (dettes)</span>
                    </div>
                    <span className="text-sm font-medium text-red-400">−{fmt(totals.passifs)}</span>
                  </div>
                </div>
              )}
              {actifs.length === 0 && (
                <p className="text-slate-600 text-sm">Aucun actif pour ce mois.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
