"use client";
import { useState, useEffect, useCallback, useRef } from "react";

import { API_BASE } from "@/lib/config";

const fmt = (v: number) =>
  v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });

interface Category { id: number; name: string; color: string }
interface Transaction {
  id: number;
  account_id: number;
  account_name: string | null;
  bank: string | null;
  date: string;
  label: string;
  raw_label: string;
  amount: number;
  type: string;
  category_id: number | null;
  category_name: string | null;
  category_color: string | null;
  category_source: string | null;
  is_internal_transfer: boolean;
  is_neutral: boolean;
  is_investment: boolean;
  is_compte_pro: boolean;
}

interface PreviewTx {
  id: number;
  date: string;
  label: string;
  amount: number;
  type: string;
  bank: string | null;
  account_name: string | null;
  category_id: number | null;
  category_name: string | null;
  category_color: string | null;
  category_source: string | null;
}

interface PendingAssign {
  txId: number;
  categoryId: number;
  preview: { count: number; transactions: PreviewTx[] } | null;
  loadingPreview: boolean;
}

export default function TransactionsPage() {
  const [transactions, setTransactions]     = useState<Transaction[]>([]);
  const [categories, setCategories]         = useState<Category[]>([]);
  const [groups, setGroups]                 = useState<{ id: number; name: string; color: string; categories: Category[] }[]>([]);
  const [months, setMonths]                 = useState<string[]>([]);
  const [monthsLoaded, setMonthsLoaded]     = useState(false);
  const [selectedMonth, setSelectedMonth]   = useState("");
  const [filterUncategorized, setFilterUncategorized] = useState(false);
  const [filterBank, setFilterBank]         = useState("");
  const [total, setTotal]                   = useState(0);
  const [loading, setLoading]               = useState(false);
  const [toastMsg, setToastMsg]             = useState<string | null>(null);
  const [newCatName, setNewCatName]         = useState("");
  const [newCatColor, setNewCatColor]       = useState("#6b7280");
  const [showNewCat, setShowNewCat]         = useState(false);
  const [pendingAssign, setPendingAssign]   = useState<PendingAssign | null>(null);
  const [recatLoading, setRecatLoading]     = useState(false);
  const [sortBy, setSortBy]                 = useState<"date" | "amount">("date");
  const [sortDir, setSortDir]               = useState<"asc" | "desc">("desc");
  const newCatRef                           = useRef<HTMLInputElement>(null);
  const loadSeqRef                          = useRef(0);

  function toggleSort(col: "date" | "amount") {
    if (sortBy === col) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortBy(col); setSortDir("desc"); }
  }

  useEffect(() => {
    fetch(`${API_BASE}/categories/`).then(r => r.json()).then(setCategories).catch(() => {});
    fetch(`${API_BASE}/category-groups/`).then(r => r.json()).then(setGroups).catch(() => {});
    fetch(`${API_BASE}/patrimony/months`)
      .then(r => r.json())
      .then((ms: string[]) => {
        setMonths(ms);
        if (ms.length > 0) {
          const prev = new Date();
          prev.setDate(1);
          prev.setMonth(prev.getMonth() - 1);
          const prevStr = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, "0")}`;
          setSelectedMonth(ms.includes(prevStr) ? prevStr : ms[0]);
        }
      })
      .catch(() => {})
      .finally(() => setMonthsLoaded(true));
  }, []);

  const loadTransactions = useCallback(() => {
    if (!monthsLoaded) return;
    const loadSeq = ++loadSeqRef.current;
    setLoading(true);
    const params = new URLSearchParams({ limit: "500", exclude_transfers: "false" });
    if (selectedMonth) params.set("month", selectedMonth);
    if (filterUncategorized) params.set("uncategorized", "true");
    fetch(`${API_BASE}/transactions/?${params}`)
      .then(r => r.json())
      .then(data => {
        if (loadSeq !== loadSeqRef.current) return;
        setTotal(data.total);
        setTransactions(data.items);
        setLoading(false);
      })
      .catch(() => {
        if (loadSeq === loadSeqRef.current) setLoading(false);
      });
  }, [monthsLoaded, selectedMonth, filterUncategorized]);

  useEffect(() => { loadTransactions(); }, [loadTransactions]);

  function showToast(msg: string) {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  }

  async function handleCategoryChange(txId: number, categoryId: number) {
    const res = await fetch(`${API_BASE}/categories/preview-assign?transaction_id=${txId}&category_id=${categoryId}`);
    const data = await res.json();
    if (data.count === 0) {
      // Pas d'autres transactions affectées → applique directement
      await confirmAssignDirect(txId, categoryId, true);
    } else {
      setPendingAssign({ txId, categoryId, preview: data, loadingPreview: false });
    }
  }

  async function confirmAssignDirect(txId: number, categoryId: number, saveRule: boolean) {
    const res = await fetch(`${API_BASE}/categories/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_id: txId, category_id: categoryId, save_rule: saveRule }),
    });
    const data = await res.json();
    if (data.ok) {
      if (saveRule && data.retroactive_count > 0) {
        showToast(`Catégorie appliquée à ${data.retroactive_count + 1} transaction(s)`);
      } else {
        showToast("Catégorie mise à jour");
      }
      loadTransactions();
    }
  }

  async function confirmAssign(saveRule: boolean) {
    if (!pendingAssign) return;
    const { txId, categoryId } = pendingAssign;
    setPendingAssign(null);
    await confirmAssignDirect(txId, categoryId, saveRule);
  }

  async function assignJustThis(txId: number, categoryId: number) {
    const res = await fetch(`${API_BASE}/categories/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_id: txId, category_id: categoryId, save_rule: false }),
    });
    const data = await res.json();
    if (data.ok) { showToast("Catégorie mise à jour"); loadTransactions(); }
  }

  async function createCategory() {
    const name = newCatName.trim();
    if (!name) return;
    const res = await fetch(`${API_BASE}/categories/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, color: newCatColor }),
    });
    if (res.ok) {
      const cat = await res.json();
      setCategories(prev => [...prev, cat].sort((a, b) => a.name.localeCompare(b.name)));
      setNewCatName("");
      setShowNewCat(false);
      showToast(`Catégorie "${cat.name}" créée`);
    } else {
      const err = await res.json();
      showToast(err.detail ?? "Erreur");
    }
  }

  async function toggleTransfer(txId: number) {
    await fetch(`${API_BASE}/transactions/${txId}/transfer`, { method: "PATCH" });
    loadTransactions();
  }

  async function toggleNeutral(txId: number) {
    await fetch(`${API_BASE}/transactions/${txId}/neutral`, { method: "PATCH" });
    loadTransactions();
  }

  async function toggleInvestment(txId: number) {
    await fetch(`${API_BASE}/transactions/${txId}/investment`, { method: "PATCH" });
    loadTransactions();
  }

  async function toggleComptePro(txId: number) {
    await fetch(`${API_BASE}/transactions/${txId}/compte-pro`, { method: "PATCH" });
    loadTransactions();
  }

  async function detectTransfers() {
    const res = await fetch(`${API_BASE}/transactions/detect-transfers`, { method: "POST" });
    const data = await res.json();
    showToast(`${data.detected} virement(s) interne(s) détecté(s)`);
    loadTransactions();
  }

  async function recategorizeAll() {
    setRecatLoading(true);
    const res = await fetch(`${API_BASE}/categories/recategorize-all`, { method: "POST" });
    const data = await res.json();
    showToast(`${data.updated} transaction(s) re-catégorisée(s) sur ${data.total}`);
    setRecatLoading(false);
    loadTransactions();
  }

  const fmtMonth = (m: string) => {
    const [y, mo] = m.split("-");
    return new Date(Number(y), Number(mo) - 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
  };

  const banks = Array.from(new Set(transactions.map(t => t.bank).filter(Boolean))) as string[];

  const displayed = transactions
    .filter(t => {
      if (filterBank && t.bank !== filterBank) return false;
      return true;
    })
    .sort((a, b) => {
      const mul = sortDir === "desc" ? -1 : 1;
      if (sortBy === "amount") return mul * (a.amount - b.amount);
      return mul * a.date.localeCompare(b.date);
    });

  const uncategorizedCount = transactions.filter(t => !t.category_id && !t.is_internal_transfer).length;

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Transactions</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {total} opérations
            {uncategorizedCount > 0 && (
              <span className="ml-2 text-amber-400">{uncategorizedCount} non catégorisées</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setShowNewCat(v => !v); setTimeout(() => newCatRef.current?.focus(), 50); }}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            + Catégorie
          </button>
          <button
            onClick={detectTransfers}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            Détecter virements
          </button>
          <button
            onClick={recategorizeAll}
            disabled={recatLoading}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-50"
          >
            {recatLoading ? "En cours…" : "Re-catégoriser tout"}
          </button>
          {banks.length > 1 && (
            <select
              value={filterBank}
              onChange={e => setFilterBank(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none"
            >
              <option value="">Toutes les banques</option>
              {banks.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          )}
          <button
            onClick={() => setFilterUncategorized(v => !v)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              filterUncategorized
                ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
                : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200"
            }`}
          >
            {filterUncategorized ? "Toutes" : `Non catégorisées (${uncategorizedCount})`}
          </button>
          <select
            value={selectedMonth}
            onChange={e => setSelectedMonth(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none"
          >
            <option value="">Toutes périodes</option>
            {months.map(m => <option key={m} value={m}>{fmtMonth(m)}</option>)}
          </select>
        </div>
      </div>

      {/* Création catégorie */}
      {showNewCat && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-3">
          <input
            ref={newCatRef}
            value={newCatName}
            onChange={e => setNewCatName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && createCategory()}
            placeholder="Nom de la catégorie..."
            className="flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
          />
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-500">Couleur</label>
            <input type="color" value={newCatColor} onChange={e => setNewCatColor(e.target.value)}
              className="w-8 h-8 rounded cursor-pointer bg-transparent border-0" />
          </div>
          <button onClick={createCategory} disabled={!newCatName.trim()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm rounded-lg transition-colors">
            Créer
          </button>
          <button onClick={() => setShowNewCat(false)} className="text-slate-500 hover:text-slate-300 text-sm">✕</button>
        </div>
      )}

      {/* Preview panel */}
      {pendingAssign && (
        <div className="bg-slate-900 border border-indigo-500/30 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              {pendingAssign.loadingPreview ? (
                <p className="text-sm text-slate-400">Recherche des transactions similaires…</p>
              ) : (
                <p className="text-sm text-slate-300">
                  <span className="text-indigo-400 font-medium">{pendingAssign.preview?.count ?? 0} autre(s) transaction(s)</span> avec le même libellé seront mises à jour.
                </p>
              )}
            </div>
            <button onClick={() => setPendingAssign(null)} className="text-slate-500 hover:text-slate-300 text-sm">✕</button>
          </div>

          {!pendingAssign.loadingPreview && pendingAssign.preview && pendingAssign.preview.count > 0 && (() => {
            const uncatList = pendingAssign.preview.transactions.filter(t => !t.category_id);
            const alreadyCatList = pendingAssign.preview.transactions.filter(t => t.category_id);
            return (
              <div className="max-h-48 overflow-y-auto space-y-1">
                {/* Non catégorisées */}
                {uncatList.map(t => (
                  <div key={t.id} className="flex items-center justify-between text-xs py-1 border-b border-slate-800/60">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-slate-500 shrink-0">{t.date}</span>
                      <span className="text-slate-300 truncate">{t.label}</span>
                      {t.account_name && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/15 text-blue-400 shrink-0">{t.account_name}</span>}
                    </div>
                    <span className="text-slate-400 shrink-0 ml-3">{fmt(t.amount)}</span>
                  </div>
                ))}
                {/* Déjà catégorisées automatiquement */}
                {alreadyCatList.length > 0 && (
                  <>
                    <p className="text-[10px] text-slate-600 pt-1 pb-0.5">Déjà catégorisées (auto) — seront remplacées :</p>
                    {alreadyCatList.map(t => (
                      <div key={t.id} className="flex items-center justify-between text-xs py-1 border-b border-slate-800/40 opacity-70">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-slate-500 shrink-0">{t.date}</span>
                          <span className="text-slate-400 truncate">{t.label}</span>
                          {t.account_name && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/15 text-blue-400 shrink-0">{t.account_name}</span>}
                          {t.category_name && (
                            <span
                              className="text-[9px] px-1.5 py-0.5 rounded shrink-0"
                              style={{ backgroundColor: `${t.category_color}25`, color: t.category_color ?? "#94a3b8" }}
                            >
                              {t.category_name}
                            </span>
                          )}
                        </div>
                        <span className="text-slate-500 shrink-0 ml-3">{fmt(t.amount)}</span>
                      </div>
                    ))}
                  </>
                )}
                {pendingAssign.preview.count > 30 && (
                  <p className="text-xs text-slate-600 text-center pt-1">… et {pendingAssign.preview.count - 30} autres</p>
                )}
              </div>
            );
          })()}

          {!pendingAssign.loadingPreview && (
            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={() => confirmAssign(true)}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg transition-colors"
              >
                Appliquer à {(pendingAssign.preview?.count ?? 0) + 1} transaction(s)
              </button>
              <button
                onClick={() => confirmAssign(false)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs rounded-lg transition-colors"
              >
                Juste celle-ci
              </button>
              <button onClick={() => setPendingAssign(null)} className="text-xs text-slate-500 hover:text-slate-300 px-2">
                Annuler
              </button>
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left">
              <th className="px-4 py-3 w-24">
                <button onClick={() => toggleSort("date")}
                  className={`text-xs font-medium flex items-center gap-1 hover:text-white transition-colors ${sortBy === "date" ? "text-indigo-400" : "text-slate-500"}`}>
                  Date {sortBy === "date" ? (sortDir === "desc" ? "↓" : "↑") : <span className="text-slate-700">↕</span>}
                </button>
              </th>
              <th className="px-4 py-3 text-xs text-slate-500 font-medium">Libellé</th>
              <th className="px-4 py-3 text-right w-28">
                <button onClick={() => toggleSort("amount")}
                  className={`text-xs font-medium flex items-center gap-1 ml-auto hover:text-white transition-colors ${sortBy === "amount" ? "text-indigo-400" : "text-slate-500"}`}>
                  {sortBy === "amount" ? (sortDir === "desc" ? "↓" : "↑") : <span className="text-slate-700">↕</span>} Montant
                </button>
              </th>
              <th className="px-4 py-3 text-xs text-slate-500 font-medium w-48">Catégorie</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-600">Chargement…</td></tr>
            )}
            {!loading && displayed.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-600">Aucune transaction</td></tr>
            )}
            {!loading && displayed.map(tx => (
              <tr
                key={tx.id}
                className={`border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors ${pendingAssign?.txId === tx.id ? "bg-indigo-500/5" : ""}`}
              >
                <td className="px-4 py-3 text-slate-500 text-xs tabular-nums">{tx.date}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <p className="text-slate-200 truncate max-w-xs" title={tx.raw_label}>{tx.label}</p>
                    {tx.account_name && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 shrink-0 border border-blue-500/20">{tx.account_name}</span>
                    )}
                  </div>
                  {tx.is_compte_pro ? (
                    <span className="text-[10px] text-orange-400">apport compte pro <span className="text-slate-600">(déduit des revenus)</span></span>
                  ) : tx.is_internal_transfer && (
                    <span className="text-[10px] text-indigo-400">virement interne</span>
                  )}
                  {tx.is_neutral && (
                    <span className="text-[10px] text-slate-400">neutre</span>
                  )}
                  {tx.is_investment && (
                    <span className="text-[10px] text-emerald-500">investissement</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  <span className={tx.type === "credit" ? "text-emerald-400 font-medium" : "text-slate-300"}>
                    {tx.type === "credit" ? "+" : "−"}{fmt(tx.amount)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {!tx.is_internal_transfer && !tx.is_investment && !tx.is_compte_pro && !tx.is_neutral && (
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-1.5">
                          <select
                            value={pendingAssign?.txId === tx.id ? pendingAssign.categoryId : (tx.category_id ?? "")}
                            onChange={e => e.target.value && handleCategoryChange(tx.id, Number(e.target.value))}
                            className={`flex-1 text-xs rounded-lg px-2 py-1.5 outline-none border transition-colors ${
                              tx.category_id
                                ? "bg-slate-800 border-slate-700 text-slate-300"
                                : "bg-amber-500/5 border-amber-500/30 text-amber-400"
                            }`}
                          >
                            <option value="">— non catégorisée —</option>
                            {groups.filter(g => g.categories.length > 0).map(g => (
                              <optgroup key={g.id} label={`— ${g.name} —`}>
                                {g.categories.map(c => (
                                  <option key={c.id} value={c.id}>{c.name}</option>
                                ))}
                              </optgroup>
                            ))}
                            {(() => {
                              const assignedIds = new Set(groups.flatMap(g => g.categories.map(c => c.id)));
                              const unassigned  = categories.filter(c => !assignedIds.has(c.id));
                              return unassigned.length > 0 ? (
                                <optgroup label="— Autres —">
                                  {unassigned.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                </optgroup>
                              ) : null;
                            })()}
                          </select>
                          {tx.category_source === "auto" && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400 shrink-0">auto</span>
                          )}
                          {tx.category_source === "manual" && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-400 shrink-0">manuel</span>
                          )}
                        </div>
                        {tx.category_id && (
                          <button
                            onClick={() => assignJustThis(tx.id, tx.category_id!)}
                            className="text-[9px] text-slate-600 hover:text-slate-400 transition-colors"
                            title="Modifier uniquement cette transaction sans affecter les autres"
                          >
                            ↳ modifier juste celle-ci
                          </button>
                        )}
                      </div>
                    )}
                    <button
                      onClick={() => toggleTransfer(tx.id)}
                      title={tx.is_internal_transfer ? "Marquer comme externe" : "Marquer comme virement interne"}
                      className={`text-[10px] px-2 py-1 rounded border shrink-0 transition-colors ${
                        tx.is_internal_transfer
                          ? "bg-indigo-500/15 border-indigo-500/30 text-indigo-400"
                          : "bg-slate-800 border-slate-700 text-slate-600 hover:text-slate-400"
                      }`}
                    >
                      ⇄
                    </button>
                    <button
                      onClick={() => toggleComptePro(tx.id)}
                      title={tx.is_compte_pro ? "Retirer le flag compte pro" : "Apport compte pro (déduit des revenus)"}
                      className={`text-[10px] px-2 py-1 rounded border shrink-0 transition-colors ${
                        tx.is_compte_pro
                          ? "bg-orange-500/15 border-orange-500/30 text-orange-400"
                          : "bg-slate-800 border-slate-700 text-slate-600 hover:text-slate-400"
                      }`}
                    >
                      💼
                    </button>
                    <button
                      onClick={() => toggleInvestment(tx.id)}
                      title={tx.is_investment ? "Retirer le flag investissement" : "Marquer comme investissement / épargne"}
                      className={`text-[10px] px-2 py-1 rounded border shrink-0 transition-colors ${
                        tx.is_investment
                          ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                          : "bg-slate-800 border-slate-700 text-slate-600 hover:text-slate-400"
                      }`}
                    >
                      📈
                    </button>
                    <button
                      onClick={() => toggleNeutral(tx.id)}
                      title={tx.is_neutral ? "Retirer le flag neutre" : "Marquer comme flux neutre (créance, prêt...)"}
                      className={`text-[10px] px-2 py-1 rounded border shrink-0 transition-colors font-medium ${
                        tx.is_neutral
                          ? "bg-slate-400/20 border-slate-400/50 text-slate-300"
                          : "bg-slate-800 border-slate-700 text-slate-600 hover:text-slate-400"
                      }`}
                    >
                      ∅
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Toast */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 bg-emerald-600 text-white text-sm px-4 py-3 rounded-xl shadow-lg animate-fade-in">
          {toastMsg}
        </div>
      )}
    </div>
  );
}
