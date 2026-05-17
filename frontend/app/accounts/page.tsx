import AccountsClient from "@/components/AccountsClient";
import { API_BASE } from "@/lib/config";

async function getMonths(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/patrimony/months`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export default async function AccountsPage() {
  const months = await getMonths();
  return <AccountsClient months={months} />;
}
