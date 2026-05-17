"use client";
import { useMemo, useState, useEffect } from "react";
import {
  ComposedChart, Area, XAxis, YAxis, CartesianGrid,
  ReferenceLine, ReferenceDot, ResponsiveContainer,
} from "recharts";
import { futureValue, monthsToTarget, fmtYears } from "@/lib/simulator";

const fmtFull = (n: number) => Math.round(n).toLocaleString("fr-FR") + " €";

interface MilestonePoint {
  target: number;
  years: number;   // negative = already reached in the past, positive = upcoming
  color: string;
  reached: boolean;
}

interface Props {
  capital: number;
  monthly: number;
  annualRate: number;
  milestonePoints: MilestonePoint[];
  totalYears: number;
  finalGoal: number;
}

// ─── Dot label for milestones ─────────────────────────────────────────────────

interface DotLabelProps {
  viewBox?: { cx: number; cy: number };
  target: number;
  years: number;
  color: string;
  above: boolean;
}

function MilestoneDotLabel({ viewBox, target, years, color, above }: DotLabelProps) {
  if (!viewBox || isNaN(viewBox.cx) || isNaN(viewBox.cy)) return null;
  const { cx, cy } = viewBox;
  const w = 116, h = 36, r = 5;
  const offsetY = above ? -(h + 14) : 14;
  const x = cx - w / 2;
  const y = cy + offsetY;
  const isPast = years < 0;
  const timeText = isPast ? `il y a ${fmtYears(-years)}` : fmtYears(years);
  return (
    <g>
      <line
        x1={cx} y1={cy + (above ? -8 : 8)}
        x2={cx} y2={cy + offsetY + (above ? h : 0)}
        stroke={color} strokeWidth={1} strokeOpacity={0.45}
      />
      <rect x={x} y={y} width={w} height={h} rx={r}
            fill="#0f172a" stroke={color} strokeWidth={1.5} fillOpacity={0.92} />
      <text x={cx} y={y + 14} textAnchor="middle" fill={color} fontSize={11} fontWeight={700}>
        {fmtFull(target)}
      </text>
      <text x={cx} y={y + 28} textAnchor="middle" fill="#94a3b8" fontSize={10}>
        {timeText}
      </text>
    </g>
  );
}

// ─── Main chart ───────────────────────────────────────────────────────────────

export default function MilestonesChart({
  capital, monthly, annualRate,
  milestonePoints, totalYears, finalGoal,
}: Props) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const monthlyRate = annualRate / 100 / 12;

  // How many years back to show (time from 0 to current capital, capped at 20)
  const pastExtent = useMemo(() => {
    if (capital <= 0) return 0;
    const months = monthsToTarget(0, monthlyRate, monthly, capital);
    return months !== null ? Math.min(months / 12, 20) : 20;
  }, [capital, monthly, monthlyRate]);

  const data = useMemo(() => {
    const steps = 300;
    const totalSpan = pastExtent + totalYears;
    if (totalSpan <= 0) return [];
    const epsilon = totalSpan / steps / 2;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const years = -pastExtent + (totalSpan * i) / steps;
      const value = years <= 0
        ? futureValue(0, monthlyRate, (years + pastExtent) * 12, monthly)
        : futureValue(capital, monthlyRate, years * 12, monthly);
      return {
        year: parseFloat(years.toFixed(3)),
        past:   years <= epsilon ? value : undefined,
        future: years >= -epsilon ? value : undefined,
      };
    });
  }, [capital, monthly, monthlyRate, totalYears, pastExtent]);

  if (!mounted) return <div className="h-[260px] bg-slate-900/30 rounded-lg animate-pulse" />;

  const maxY = finalGoal * 1.06;
  const tickY = (v: number) => {
    if (v >= 1_000_000) return `${Math.round(v / 1_000_000)}M€`;
    if (v >= 1_000) return `${Math.round(v / 1_000)}k€`;
    return `${v}€`;
  };

  const tickX = (v: number) => {
    if (v === 0) return "Auj.";
    if (v < 0) return `−${Math.abs(Math.round(v))} ans`;
    return `${Math.round(v)} ans`;
  };

  const reachedPoints = milestonePoints.filter((p) => p.reached);
  const upcomingPoints = milestonePoints.filter((p) => !p.reached);

  return (
    <ResponsiveContainer width="100%" height={290}>
      <ComposedChart data={data} margin={{ top: 55, right: 30, bottom: 20, left: 50 }}>
        <defs>
          <linearGradient id="milPastGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#475569" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#475569" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="milFutureGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />

        <XAxis
          dataKey="year"
          type="number"
          scale="linear"
          domain={[-pastExtent, totalYears]}
          tickCount={8}
          tickFormatter={tickX}
          stroke="#334155"
          tick={{ fill: "#64748b", fontSize: 10 }}
        />
        <YAxis
          domain={[0, maxY]}
          tickFormatter={tickY}
          stroke="#334155"
          tick={{ fill: "#64748b", fontSize: 10 }}
          tickCount={6}
        />

        {/* Past: grey */}
        <Area
          dataKey="past"
          stroke="#475569"
          strokeWidth={2}
          fill="url(#milPastGrad)"
          dot={false}
          activeDot={false}
          connectNulls={false}
          isAnimationActive={false}
        />

        {/* Future: indigo */}
        <Area
          dataKey="future"
          stroke="#6366f1"
          strokeWidth={2.5}
          fill="url(#milFutureGrad)"
          dot={false}
          activeDot={false}
          connectNulls={false}
          isAnimationActive={false}
        />

        {/* Today marker */}
        <ReferenceLine
          x={0}
          stroke="#64748b"
          strokeDasharray="3 3"
          strokeOpacity={0.7}
          strokeWidth={1.5}
          label={{ value: "Auj.", position: "insideTopRight", fill: "#94a3b8", fontSize: 9 }}
        />

        {/* Upcoming milestones: dashed horizontal + colored dot + label */}
        {upcomingPoints.map((p) => (
          <ReferenceLine
            key={`u-${p.target}`}
            y={p.target}
            stroke={p.color}
            strokeDasharray="4 4"
            strokeOpacity={0.45}
            strokeWidth={1.5}
          />
        ))}

        {upcomingPoints.map((p, i) => (
          <ReferenceDot
            key={`dot-${p.target}`}
            x={p.years}
            y={p.target}
            r={7}
            fill={p.color}
            stroke="#0f172a"
            strokeWidth={2}
            label={
              <MilestoneDotLabel
                target={p.target}
                years={p.years}
                color={p.color}
                above={i % 2 === 0}
              />
            }
          />
        ))}

        {/* Reached milestones: muted dot in the past + "il y a X" label */}
        {reachedPoints.map((p, i) => (
          <ReferenceDot
            key={`dot-past-${p.target}`}
            x={p.years}
            y={p.target}
            r={5}
            fill="#475569"
            stroke="#0f172a"
            strokeWidth={2}
            label={
              <MilestoneDotLabel
                target={p.target}
                years={p.years}
                color="#64748b"
                above={i % 2 !== 0}
              />
            }
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
