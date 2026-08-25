import { ReactNode } from "react";

import Sidebar from "@/components/Sidebar";
import ProtectedRoute from "@/components/ProtectedRoute";

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({
  children,
}: DashboardLayoutProps) {
  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-[#0f0f0f]">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6 text-white">{children}</main>
      </div>
    </ProtectedRoute>
  );
}
