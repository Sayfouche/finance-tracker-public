import type { Metadata } from "next";
import "./globals.css";
import EnvironmentBanner from "@/components/EnvironmentBanner";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Finance Tracker",
  description: "Gestion financière personnelle",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="h-full">
      <body className="flex h-screen bg-slate-950 overflow-hidden antialiased">
        <Sidebar />
        <div className="flex-1 min-w-0 flex flex-col">
          <EnvironmentBanner />
          <main className="flex-1 overflow-y-auto p-6 lg:p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
