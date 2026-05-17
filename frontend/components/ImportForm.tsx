"use client";
import { useState, useRef } from "react";
import { Upload, CheckCircle, AlertCircle } from "lucide-react";
import type { Account } from "@/lib/api";

import { API_BASE } from "@/lib/config";

interface Props { accounts: Account[] }

interface SkippedRow {
  date: string;
  label: string;
  amount: number;
  type: string;
  reason: string;
}

interface ImportResult {
  account: string;
  created: number;
  skipped: number;
  errors: number;
  internal_transfers_detected: number;
  skipped_detail: SkippedRow[];
}

export default function ImportForm({ accounts }: Props) {
  const [accountId, setAccountId] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSkipped, setShowSkipped] = useState(false);
  const [forcedRows, setForcedRows] = useState<Set<number>>(new Set());
  const [forcingRow, setForcingRow] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function forceImport(row: SkippedRow, index: number) {
    setForcingRow(index);
    try {
      await fetch(`${API_BASE}/transactions/force-create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: Number(accountId),
          date: row.date,
          raw_label: row.label,
          amount: row.amount,
          type: row.type || "debit",
        }),
      });
      setForcedRows(prev => new Set([...prev, index]));
    } finally {
      setForcingRow(null);
    }
  }

  async function handleImport() {
    if (!file || !accountId) return;
    setLoading(true);
    setResult(null);
    setError(null);
    setForcedRows(new Set());

    const form = new FormData();
    form.append("account_id", accountId);
    form.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/transactions/import`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Erreur import");
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Zone upload */}
      <div
        className="bg-slate-900 border-2 border-dashed border-slate-700 hover:border-indigo-500/50 rounded-xl p-12 text-center transition-colors cursor-pointer"
        onClick={() => inputRef.current?.click()}
      >
        <input ref={inputRef} type="file" accept=".csv,.xls,.xlsx"
          className="hidden" onChange={e => setFile(e.target.files?.[0] ?? null)} />
        <div className="mx-auto w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
          <Upload size={18} className="text-indigo-400" />
        </div>
        {file ? (
          <p className="text-indigo-300 font-medium">{file.name}</p>
        ) : (
          <>
            <p className="text-slate-300 font-medium">Glissez un fichier ici</p>
            <p className="text-slate-500 text-sm mt-1">CSV ou Excel (.xls, .xlsx)</p>
          </>
        )}
      </div>

      {/* Sélection compte + bouton */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div>
          <label className="text-xs text-slate-400 mb-1.5 block">Associer à un compte</label>
          <select
            value={accountId}
            onChange={e => setAccountId(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2.5 outline-none"
          >
            <option value="">Sélectionner un compte...</option>
            {accounts.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
        <button
          disabled={!file || !accountId || loading}
          onClick={handleImport}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? "Import en cours..." : "Importer"}
        </button>
      </div>

      {/* Résultat */}
      {result && (
        <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle size={16} className="text-emerald-400" />
            <p className="text-sm font-semibold text-emerald-300">Import réussi — {result.account}</p>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="bg-slate-900 rounded-lg p-3">
              <p className="text-slate-400 text-xs">Créées</p>
              <p className="text-white font-bold text-lg">{result.created}</p>
            </div>
            <button
              onClick={() => setShowSkipped(v => !v)}
              className="bg-slate-900 rounded-lg p-3 text-left hover:bg-slate-800 transition-colors"
            >
              <p className="text-slate-400 text-xs">Ignorées {result.skipped > 0 && <span className="text-indigo-400 underline">(voir détail)</span>}</p>
              <p className="text-white font-bold text-lg">{result.skipped}</p>
            </button>
            <div className="bg-slate-900 rounded-lg p-3">
              <p className="text-slate-400 text-xs">Virements internes</p>
              <p className="text-indigo-400 font-bold text-lg">{result.internal_transfers_detected}</p>
            </div>
            <div className="bg-slate-900 rounded-lg p-3">
              <p className="text-slate-400 text-xs">Erreurs</p>
              <p className={`font-bold text-lg ${result.errors > 0 ? "text-red-400" : "text-white"}`}>{result.errors}</p>
            </div>
          </div>

          {showSkipped && result.skipped_detail?.length > 0 && (
            <div className="mt-4 border-t border-slate-700 pt-4 space-y-1">
              <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider">
                Lignes ignorées — cliquez sur &ldquo;Accepter&rdquo; pour forcer l&apos;import
              </p>
              {result.skipped_detail.map((row, i) => (
                <div key={i} className={`flex items-center justify-between text-xs py-1.5 border-b border-slate-800 ${forcedRows.has(i) ? "opacity-40" : ""}`}>
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-slate-500 shrink-0">{row.date}</span>
                    <span className="text-slate-300 truncate">{row.label || "—"}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <span className="text-slate-400">{row.amount > 0 ? `${row.amount.toLocaleString("fr-FR")} €` : "—"}</span>
                    <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 text-[10px]">{row.reason}</span>
                    {row.reason === "doublon" && !forcedRows.has(i) && (
                      <button
                        onClick={() => forceImport(row, i)}
                        disabled={forcingRow === i}
                        className="px-2 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 text-[10px] hover:bg-indigo-500/25 transition-colors disabled:opacity-50"
                      >
                        {forcingRow === i ? "…" : "Accepter"}
                      </button>
                    )}
                    {forcedRows.has(i) && (
                      <span className="text-emerald-400 text-[10px]">✓ importée</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-4 flex items-center gap-2">
          <AlertCircle size={16} className="text-red-400" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}
    </div>
  );
}
