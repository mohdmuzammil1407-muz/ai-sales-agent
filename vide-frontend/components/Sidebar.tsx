"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { clearAdminSession } from "@/lib/auth";

const navigationItems = [
  { href: "/dashboard", label: "Overview", icon: "📊" },
  { href: "/dashboard/leads", label: "Leads", icon: "📌" },
  { href: "/dashboard/chats", label: "Chats", icon: "💬" },
  { href: "/dashboard/meetings", label: "Meetings", icon: "📅" },
  { href: "/dashboard/emails", label: "Emails", icon: "✉️" },
];

const Sidebar = () => {
  const pathname = usePathname();

  const handleLogout = () => {
    clearAdminSession();
    window.location.href = "/login";
  };

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-white/5 bg-[#141414] px-4 py-6 text-white">
      <div className="px-3">
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">
          Ilmora Studios
        </p>
        <h2 className="mt-3 text-xl font-semibold">Admin Panel</h2>
      </div>

      <nav className="mt-8 flex-1 space-y-2">
        {navigationItems.map((item) => {
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-xl px-3 py-3 text-sm font-medium transition ${
                isActive
                  ? "bg-[#7c3aed] text-white"
                  : "text-zinc-300 hover:bg-white/5 hover:text-white"
              }`}
            >
              <span className="mr-3">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <button
        type="button"
        onClick={handleLogout}
        className="rounded-xl border border-white/10 px-3 py-3 text-sm font-medium text-zinc-200 transition hover:bg-white/5 hover:text-white"
      >
        Logout
      </button>
    </aside>
  );
};

export default Sidebar;
