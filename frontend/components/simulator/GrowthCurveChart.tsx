"use client";
import { useMemo, useState, useEffect } from "react";
import {
  ComposedChart, Area, XAxis, YAxis, CartesianGrid,
  ReferenceLine, ReferenceDot, ResponsiveContainer, Customized,
} from "recharts";
import { futureValue, monthsToTarget, fmtYears } from "@/lib/simulator";

const fmtFull = (n: number) => Math.round(n).toLocaleString("fr-FR") + " €";

interface Props {
  capital: number;
  monthly: number;
  annualRate: number;
  halfYears: number;
  totalYears: number;
  halfCapital: number;
  finalGoal: number;
}

// ─── Annotation boxes rendered via SVG inside the chart ───────────────────────

interface AxisSpec { scale: (v: number) => number }
interface AnnotationProps {
  xAxisMap?: Record<string, AxisSpec>;
  yAxisMap?: Record<string, AxisSpec>;
  capital: number;
  halfYears: number;
  halfCapital: number;
  totalYears: number;
  finalGoal: number;
}

function AnnotationBoxes({
  xAxisMap, yAxisMap,
  capital, halfYears, halfCapital, totalYears, finalGoal,
}: AnnotationProps) {
  if (!xAxisMap || !yAxisMap) return null;
  const xAxis = (Object.values(xAxisMap) as AxisSpec[])[0];
  const yAxis = (Object.values(yAxisMap) as AxisSpec[])[0];
  if (!xAxis?.scale || !yAxis?.scale) return null;

  const tx = (v: number) => xAxis.scale(v) as number;
  const ty = (v: number) => yAxis.scale(v) as number;

  const box = (
    cx: number, cy: number,
    line1: string, line2: string,
    color: string
  ) => {
    const w = 148, h = 46, r = 6;
    return (
      <g>
        <rect
          x={cx - w / 2} y={cy - h / 2}
          width={w} height={h} rx={r}
          fill="#0f172a" stroke={color} strokeWidth={1.5} fillOpacity={0.92}
        />
        <text x={cx} y={cy - 5} textAnchor="middle" fill="white" fontSize={11} fontWeight={600}>
          {line1}
        </text>
        <text x={cx} y={cy + 12} textAnchor="middle" fill={color} fontSize={10}>
          {line2}
        </text>
      </g>
    );
  };

  // Annotation boxes between x=0 (today) and future milestones
  const box1cx = (tx(0) + tx(halfYears)) / 2;
  const box1cy = (ty(capital) + ty(halfCapital)) / 2 - 50;

  const box2cx = (tx(halfYears) + tx(totalYears)) / 2;
  const box2cy = (ty(halfCapital) + ty(finalGoal)) / 2 - 50;

  if ([box1cx, box1cy, box2cx, box2cy].some(isNaN)) return null;

  return (
    <g>
      {box(box1cx, box1cy, `0 → ${fmtFull(halfCapital)}`, fmtYears(halfYears), "#60a5fa")}
      {box(box2cx, box2cy, `${fmtFull(halfCapital)} → ${fmtFull(finalGoal)}`, fmtYears(totalYears - halfYears), "#4ade80")}
    </g>
  );
}

// ─── Main chart ───────────────────────────────────────────────────────────────

export default function GrowthCurveChart({
  capital, monthly, annualRate,
  halfYears, totalYears, halfCapital, finalGoal,
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
    const epsilon = totalSpan / steps / 2;
    const result = [];
    for (let i = 0; i <= steps; i++) {
      const years = -pastExtent + (totalSpan * i) / steps;
      // Single value formula: past from 0, future from capital
      const value = years <= 0
        ? futureValue(0, monthlyRate, (years + pastExtent) * 12, monthly)
        : futureValue(capital, monthlyRate, years * 12, monthly);
      result.push({
        year: parseFloat(years.toFixed(3)),
        // Slight overlap at boundaries ensures smooth visual connection
        past:   years <= epsilon ? value : undefined,
        first:  years >= -epsilon && years <= halfYears + epsilon ? value : undefined,
        second: years >= halfYears - epsilon ? value : undefined,
      });
    }
    return result;
  }, [capital, monthly, monthlyRate, halfYears, totalYears, pastExtent]);

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

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 20, right: 30, bottom: 20, left: 50 }}>
        <defs>
          <linearGradient id="simPastGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#475569" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#475569" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="simFirstGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="simSecondGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
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

        {/* Today marker */}
        <ReferenceLine
          x={0}
          stroke="#64748b"
          strokeDasharray="3 3"
          strokeOpacity={0.7}
          strokeWidth={1.5}
          label={{ value: "Auj.", position: "insideTopRight", fill: "#94a3b8", fontSize: 9 }}
        />

        {/* Half-capital and final goal reference lines */}
        <ReferenceLine
          y={halfCapital}
          stroke="#f59e0b"
          strokeDasharray="5 4"
          strokeOpacity={0.55}
          strokeWidth={1.5}
        />
        <ReferenceLine
          y={finalGoal}
          stroke="#22c55e"
          strokeDasharray="5 4"
          strokeOpacity={0.4}
          strokeWidth={1.5}
        />
        <ReferenceLine
          x={halfYears}
          stroke="#f59e0b"
          strokeDasharray="5 4"
          strokeOpacity={0.55}
          strokeWidth={1.5}
        />

        {/* Past: grey */}
        <Area
          dataKey="past"
          stroke="#475569"
          strokeWidth={2}
          fill="url(#simPastGrad)"
          dot={false}
          activeDot={false}
          connectNulls={false}
          isAnimationActive={false}
        />

        {/* First half: blue */}
        <Area
          dataKey="first"
          stroke="#3b82f6"
          strokeWidth={2.5}
          fill="url(#simFirstGrad)"
          dot={false}
          activeDot={false}
          connectNulls={false}
          isAnimationActive={false}
        />

        {/* Second half: green */}
        <Area
          dataKey="second"
          stroke="#22c55e"
          strokeWidth={2.5}
          fill="url(#simSecondGrad)"
          dot={false}
          activeDot={false}
          connectNulls={false}
          isAnimationActive={false}
        />

        {/* Key dots: today, half milestone, final goal */}
        <ReferenceDot
          x={0} y={capital}
          r={5} fill="#64748b" stroke="#0f172a" strokeWidth={2}
        />
        <ReferenceDot
          x={halfYears} y={halfCapital}
          r={8} fill="#f59e0b" stroke="#0f172a" strokeWidth={2}
        />
        <ReferenceDot
          x={totalYears} y={finalGoal}
          r={8} fill="#22c55e" stroke="#0f172a" strokeWidth={2}
        />

        {/* Annotation boxes */}
        <Customized
          component={(props: Omit<AnnotationProps, "capital" | "halfYears" | "halfCapital" | "totalYears" | "finalGoal">) => (
            <AnnotationBoxes
              {...props}
              capital={capital}
              halfYears={halfYears}
              halfCapital={halfCapital}
              totalYears={totalYears}
              finalGoal={finalGoal}
            />
          )}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
