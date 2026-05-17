"use client";
import { useState } from "react";

interface Layer {
  key: string;
  label: string;
  value: number;
  color: string;
}

interface Indicators {
  epargne_securite: number;
  epargne_dispo: number;
  capital_investi: number;
  investi_plus_livrets: number;
  patrimoine_hors_rp: number;
  patrimoine_net: number;
  layers: Layer[];
}

interface AccountSnap {
  account_id: number;
  account_name: string;
  account_type: string;
  bank: string;
  members: string[];
  value: number | null;
}

const LAYER_TYPES: Record<string, string[]> = {
  securite:   ["courant", "livret", "epargne"],
  accessible: ["autre_actif", "assurance_vie", "cto"],
  investi_lt: ["pea", "per"],
  immo:       ["immobilier", "credit"],
};

const fmt = (v: number) =>
  v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

const fmtK = (v: number) => {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M€`;
  if (v >= 1_000)     return `${Math.round(v / 1_000)}k€`;
  return `${Math.round(v)}€`;
};

const METRICS = [
  { key: "epargne_securite",     label: "Épargne sécurité", sub: "Courants + livrets",          color: "text-emerald-400", dot: "#22c55e" },
  { key: "epargne_dispo",        label: "Épargne dispo",    sub: "Sécu + AV + CTO",              color: "text-cyan-400",    dot: "#06b6d4" },
  { key: "capital_investi",      label: "Capital investi",  sub: "CTO + PEA + PER + AV",         color: "text-indigo-400",  dot: "#6366f1" },
  { key: "investi_plus_livrets", label: "Investi + livrets",sub: "Capital investi + livrets",     color: "text-violet-400",  dot: "#8b5cf6" },
  { key: "patrimoine_hors_rp",   label: "Hors immo",        sub: "Net sans résidence principale", color: "text-amber-400",  dot: "#f59e0b" },
];

export default function LiquidityAnalysis({
  indicators,
  accounts = [],
}: {
  indicators: Indicators | null;
  accounts?: AccountSnap[];
}) {
  const [activeLayer, setActiveLayer] = useState<string | null>(null);

  if (!indicators) return null;

  const total = indicators.layers.reduce((s, l) => s + l.value, 0);

  const layerAccounts = (layerKey: string): AccountSnap[] => {
    const types = LAYER_TYPES[layerKey] ?? [];
    return accounts.filter(a => types.includes(a.account_type) && a.value !== null);
  };

  const activeLayerData = indicators.layers.find(l => l.key === activeLayer) ?? null;
  const detailAccounts  = activeLayer ? layerAccounts(activeLayer) : [];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5">
      <h3 className="text-sm font-semibold text-white">Analyse patrimoniale</h3>

      {/* Métriques clés */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {METRICS.map(({ key, label, sub, color, dot }) => {
          const value = indicators[key as keyof Indicators] as number;
          return (
            <div key={key} className="bg-slate-800/60 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: dot }} />
                <p className="text-[10px] text-slate-400 leading-tight">{label}</p>
              </div>
              <p className={`text-base font-bold ${color}`}>{fmt(value)}</p>
              <p className="text-[10px] text-slate-600 mt-0.5">{sub}</p>
            </div>
          );
        })}
      </div>

      {/* Barre de liquidité */}
      <div className="space-y-2">
        <p className="text-[10px] text-slate-500 uppercase tracking-wider">Spectre de liquidité</p>

        {/* Barre segmentée cliquable */}
        <div className="flex rounded-lg overflow-hidden h-8 gap-px">
          {indicators.layers.map((layer) => {
            const pct = total > 0 ? (layer.value / total) * 100 : 0;
            if (pct < 0.5) return null;
            const isActive = activeLayer === layer.key;
            return (
              <button
                key={layer.key}
                style={{ width: `${pct}%`, backgroundColor: layer.color }}
                className={`relative flex items-center justify-center transition-opacity cursor-pointer ${
                  isActive ? "opacity-100 ring-2 ring-white/30 ring-inset" : "opacity-75 hover:opacity-95"
                }`}
                onClick={() => setActiveLayer(isActive ? null : layer.key)}
                title={`${layer.label} : ${fmt(layer.value)}`}
              >
                {pct > 8 && (
                  <span className="text-[10px] font-semibold text-white/90 select-none truncate px-1">
                    {fmtK(layer.value)}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Légende */}
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {indicators.layers.map((layer) => {
            const pct = total > 0 ? ((layer.value / total) * 100).toFixed(1) : "0";
            return (
              <button
                key={layer.key}
                className={`flex items-center gap-1.5 transition-opacity ${
                  activeLayer && activeLayer !== layer.key ? "opacity-40" : "opacity-100"
                }`}
                onClick={() => setActiveLayer(activeLayer === layer.key ? null : layer.key)}
              >
                <div className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: layer.color }} />
                <span className="text-[11px] text-slate-400">{layer.label}</span>
                <span className="text-[11px] text-slate-600">{pct}%</span>
              </button>
            );
          })}
        </div>

        {/* Détail comptes par couche */}
        {activeLayerData && (
          <div
            className="mt-3 rounded-lg border p-3 space-y-2 transition-all"
            style={{ borderColor: `${activeLayerData.color}40`, background: `${activeLayerData.color}08` }}
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-white">{activeLayerData.label}</p>
              <p className="text-xs font-bold" style={{ color: activeLayerData.color }}>
                {fmt(activeLayerData.value)}
              </p>
            </div>
            {detailAccounts.length === 0 ? (
              <p className="text-xs text-slate-600">Aucun compte pour ce mois.</p>
            ) : (
              <div className="space-y-1">
                {detailAccounts
                  .sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0))
                  .map((acc) => {
                    const v = acc.value ?? 0;
                    const isDebt = v < 0;
                    return (
                      <div key={acc.account_id} className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs text-slate-400 truncate">{acc.account_name}</span>
                          {acc.members.length > 0 && (
                            <span className="text-[10px] text-slate-600 shrink-0">{acc.members.join(", ")}</span>
                          )}
                        </div>
                        <span className={`text-xs font-medium shrink-0 ml-3 ${isDebt ? "text-red-400" : "text-slate-200"}`}>
                          {isDebt ? "−" : ""}{fmt(Math.abs(v))}
                        </span>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
