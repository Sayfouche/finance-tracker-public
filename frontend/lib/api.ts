import { API_BASE } from "@/lib/config";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
}

// ─── Accounts ─────────────────────────────────────────────────────────────────
export const getAccounts   = () => get<Account[]>("/accounts/");
export const getAccountTotals = () => get<Totals>("/accounts/summary/totals");

// ─── Transactions ──────────────────────────────────────────────────────────────
export const getMonthlySummary = (month: string) =>
  get<MonthlySummary>(`/transactions/summary/monthly?month=${month}`);

export const getTransactions = (params: {
  account_id?: number;
  month?: string;
  limit?: number;
}) => {
  const q = new URLSearchParams();
  if (params.account_id) q.set("account_id", String(params.account_id));
  if (params.month)      q.set("month", params.month);
  if (params.limit)      q.set("limit", String(params.limit));
  return get<{ total: number; items: Transaction[] }>(`/transactions/?${q}`);
};

// ─── Categories ────────────────────────────────────────────────────────────────
export const getCategories = () => get<Category[]>("/categories/");
export const assignCategory = (transaction_id: number, category_id: number) =>
  post("/categories/assign", { transaction_id, category_id, save_rule: true });

// ─── Members ──────────────────────────────────────────────────────────────────
export const getMembers = () => get<Member[]>("/members/");

// ─── Types ────────────────────────────────────────────────────────────────────
export interface Account {
  id: number;
  name: string;
  type: string;
  bank: string | null;
  currency: string;
  initial_balance: number;
  start_date: string | null;
  status: string;
  notes: string | null;
  members: { id: number; first_name: string; role: string }[];
  current_balance: number | null;
}

export interface Totals {
  actifs: number;
  passifs: number;
  patrimoine_net: number;
}

export interface MonthlySummary {
  month: string;
  revenus: number;
  depenses: number;
  epargne: number;
  taux_epargne: number;
  categories: { name: string; color: string; total: number }[];
  virements_internes: number;
  nb_transactions: number;
}

export interface Transaction {
  id: number;
  account_id: number;
  date: string;
  label: string;
  amount: number;
  type: string;
  category_id: number | null;
  category_name: string | null;
  category_color: string | null;
  is_internal_transfer: boolean;
}

export interface Category {
  id: number;
  name: string;
  color: string;
  icon: string | null;
  is_system: boolean;
}

export interface Member {
  id: number;
  first_name: string;
  role: string;
}
