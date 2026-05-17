"use client";
import { useState, useEffect } from "react";
import {
  AreaChart, ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

interface MonthPoint {
  month: string;
  label: string;
  actifs: number;
  passifs: number;
  net: number;
}

interface NetEvolution {
  mode: string;
  series: { key: string; name: string; color: string }[];
  points: Record<string, string | number>[];
}

interface Props {
  history: MonthPoint[];
  netHistory: NetEvolution | null;
  liqHistory: NetEvolution | null;
  metricsHistory: NetEvolution | null;
  mode: "brut" | "net" | "liquidity" | "metrics";
  onModeChange: (mode: "brut" | "net" | "liquidity" | "metrics") => void;
}

const fmt = (v: number) => `${Math.round(v / 1000)}k€`;
const tooltipValue = (v: unknown, name: unknown) => [
  `${Number(v).toLocaleString("fr-FR")} €`,
  String(name),
];

export default function PatrimonyChart({ history, netHistory, liqHistory, metricsHistory, mode, onModeChange }: Props) {
  const [mounted, setMounted] = useState(false);
  const [showTotal, setShowTotal] = useState(true);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-[280px]" />;

  const activeEvolution = mode === "liquidity" ? liqHistory : mode === "metrics" ? metricsHistory : netHistory;
  const activePoints = activeEvolution?.points ?? [];
  const activeSeries = activeEvolution?.series ?? [];

  const periodLabel = (mode === "brut" ? history : activePoints).length > 0
    ? (() => {
        const data = mode === "brut" ? history : activePoints;
        return `${String(data[0].label)} → ${String(data[data.length - 1].label)}`;
      })()
    : "Aucune donnée";

  const TABS: { key: "brut" | "net" | "liquidity" | "metrics"; label: string }[] = [
    { key: "brut",      label: "Brut" },
    { key: "net",       label: "Actifs" },
    { key: "liquidity", label: "Liquidité" },
    { key: "metrics",   label: "Métriques" },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white mb-1">Évolution du patrimoine</h3>
          <p className="text-xs text-slate-500">{periodLabel}</p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {(mode === "net" || mode === "liquidity") && (
            <button
              onClick={() => setShowTotal(s => !s)}
              className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
                showTotal
                  ? "bg-indigo-600/20 border-indigo-500 text-indigo-300"
                  : "border-slate-700 text-slate-500 hover:text-slate-300"
              }`}
            >
              Patrimoine net
            </button>
          )}
          <div className="flex rounded-lg overflow-hidden border border-slate-700 text-xs">
            {TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => onModeChange(tab.key)}
                className={`px-3 py-1.5 transition-colors ${
                  mode === tab.key ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        {mode === "brut" ? (
          <AreaChart data={history}>
            <defs>
              <linearGradient id="gradActifs" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradNet" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={fmt} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={tooltipValue}
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#94a3b8" }}
            />
            <Legend formatter={(v) => <span style={{ color: "#94a3b8", fontSize: 11 }}>{v}</span>} />
            <Area type="monotone" dataKey="actifs"  name="Actifs"         stroke="#22c55e" strokeWidth={1.5} fill="url(#gradActifs)" strokeDasharray="4 2" dot={false} />
            <Area type="monotone" dataKey="passifs" name="Passifs"        stroke="#ef4444" strokeWidth={1.5} fill="none" dot={false} />
            <Area type="monotone" dataKey="net"     name="Patrimoine net" stroke="#6366f1" strokeWidth={2}   fill="url(#gradNet)" dot={false} />
          </AreaChart>
        ) : (
          <ComposedChart data={activePoints}>
            <defs>
              <linearGradient id="gradPatNet" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={fmt} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={tooltipValue}
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#94a3b8" }}
            />
            <Legend formatter={(v) => <span style={{ color: "#94a3b8", fontSize: 11 }}>{v}</span>} />
            {showTotal && (
              <Area
                type="monotone"
                dataKey="total"
                name="Patrimoine net"
                stroke="#6366f1"
                strokeWidth={2.5}
                fill="url(#gradPatNet)"
                dot={false}
              />
            )}
            {activeSeries.map((series) => (
              <Line
                key={series.key}
                type="monotone"
                dataKey={series.key}
                name={series.name}
                stroke={series.color}
                strokeWidth={1.5}
                strokeOpacity={0.6}
                dot={false}
              />
            ))}
          </ComposedChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
