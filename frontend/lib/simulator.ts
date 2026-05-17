/**
 * Computes how long ago (in years) the capital was at `pastTarget`,
 * assuming constant DCA at current rate.
 * Returns a negative number (years in the past), or 0 if already below target.
 */
export function yearsAgo(
  pastTarget: number,
  currentCapital: number,
  annualRatePct: number,
  monthlyPmt: number
): number {
  if (currentCapital <= pastTarget) return 0;
  const months = monthsToTarget(pastTarget, annualRatePct / 100 / 12, monthlyPmt, currentCapital);
  return months !== null ? -months / 12 : 0;
}

export function fmtYears(y: number): string {
  if (y <= 0) return "déjà atteint";
  let years = Math.floor(y);
  let months = Math.round((y - years) * 12);
  if (months === 12) { years += 1; months = 0; }
  if (years === 0) return `${months} mois`;
  if (months === 0) return `${years} an${years > 1 ? "s" : ""}`;
  return `${years} an${years > 1 ? "s" : ""} ${months} mois`;
}

export function fmtK(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v % 100_000 < 50_000 ? 1 : 0)}M€`;
  if (v >= 1_000) return `${Math.round(v / 1_000)}k€`;
  return `${Math.round(v)}€`;
}

export function futureValue(
  pv: number,
  monthlyRate: number,
  months: number,
  pmt: number
): number {
  if (monthlyRate === 0) return pv + pmt * months;
  const factor = Math.pow(1 + monthlyRate, months);
  return pv * factor + pmt * ((factor - 1) / monthlyRate);
}

/** Returns months to reach target, or null if unreachable within 100 years. */
export function monthsToTarget(
  pv: number,
  monthlyRate: number,
  pmt: number,
  target: number
): number | null {
  if (pv >= target) return 0;
  if (futureValue(pv, monthlyRate, 1200, pmt) < target) return null;
  let lo = 0,
    hi = 1200;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (futureValue(pv, monthlyRate, mid, pmt) < target) lo = mid;
    else hi = mid;
  }
  return hi;
}

/** Returns years to reach target, or null if unreachable. */
export function yearsToTarget(
  pv: number,
  annualRatePct: number,
  monthlyPmt: number,
  target: number
): number | null {
  const months = monthsToTarget(pv, annualRatePct / 100 / 12, monthlyPmt, target);
  return months === null ? null : months / 12;
}

export interface CrossoverResult {
  year: number;
  capitalAtCrossover: number;
  annualInterest: number;
  annualContribs: number;
}

/** Returns the first year where annual capital gain > annual contributions. */
export function capitalVsContribCrossover(
  pv: number,
  annualRatePct: number,
  monthlyPmt: number
): CrossoverResult | null {
  const monthlyRate = annualRatePct / 100 / 12;
  const annualContribs = monthlyPmt * 12;
  for (let year = 1; year <= 100; year++) {
    const capital = futureValue(pv, monthlyRate, year * 12, monthlyPmt);
    const annualInterest = capital * (annualRatePct / 100);
    if (annualInterest >= annualContribs) {
      return {
        year,
        capitalAtCrossover: Math.round(capital),
        annualInterest: Math.round(annualInterest),
        annualContribs: Math.round(annualContribs),
      };
    }
  }
  return null;
}
