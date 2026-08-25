"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BadgeCheck,
  Clock3,
  RotateCcw,
  TriangleAlert,
  Users,
} from "lucide-react";

import { adminGet } from "@/lib/apiClient";

type DashboardStatsResponse = {
  total_chats?: number;
  total_meetings?: number;
  total_leads?: number;
  pending_leads?: number;
  recent_leads?: RecentLead[];
};

type RecentLead = {
  conversation_id?: string;
  name?: string | null;
  email?: string | null;
  business_name?: string;
  recommended_package?: string;
  lead_score?: number | null;
  order_confirmed?: boolean | null;
  status?: string | null;
  created_at?: string;
};

const formatDate = (dateStr: string | null | undefined) => {
  if (!dateStr) return "—";
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};

const getScoreBadgeClass = (score: number) => {
  if (score >= 7) {
    return "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/20";
  }

  if (score >= 4) {
    return "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/20";
  }

  return "bg-red-500/15 text-red-300 ring-1 ring-red-500/20";
};

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="animate-pulse rounded-2xl border-l-4 border-l-violet-600 bg-[#1a1a1a] p-5"
          >
            <div className="h-5 w-24 rounded bg-white/10" />
            <div className="mt-4 h-9 w-20 rounded bg-white/10" />
            <div className="mt-3 h-4 w-28 rounded bg-white/10" />
          </div>
        ))}
      </div>

      <div className="rounded-2xl bg-[#1a1a1a] p-5">
        <div className="mb-5 h-6 w-40 animate-pulse rounded bg-white/10" />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <div
              key={index}
              className="h-14 animate-pulse rounded-xl bg-white/5"
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [recentLeads, setRecentLeads] = useState<RecentLead[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await adminGet<DashboardStatsResponse>("/api/v1/admin/overview");
      console.log("DASHBOARD OVERVIEW:", data);

      setStats(data ?? null);
      setRecentLeads(data?.recent_leads ?? []);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load dashboard.";
      console.error("Dashboard error:", err);
      setError(errorMessage);
      setStats(null);
      setRecentLeads([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const derivedStats = useMemo(() => {
    const totalLeads = recentLeads.length;
    const pendingLeads = recentLeads.filter((lead) => !lead?.order_confirmed).length;

    return {
      totalLeads,
      pendingLeads,
      totalChats: stats?.total_chats ?? totalLeads,
      totalMeetings: stats?.total_meetings ?? 0,
    };
  }, [recentLeads, stats?.total_chats, stats?.total_meetings]);

  const display = {
    totalChats: stats?.total_chats ?? derivedStats.totalChats,
    totalMeetings: stats?.total_meetings ?? derivedStats.totalMeetings,
    totalLeads: stats?.total_leads ?? derivedStats.totalLeads,
    pendingLeads: stats?.pending_leads ?? derivedStats.pendingLeads,
  };

  const statsList = useMemo(() => {
    return [
      {
        label: "Total Chats",
        value: display.totalChats,
        icon: Users,
        iconClassName: "text-sky-400",
      },
      {
        label: "Total Meetings",
        value: display.totalMeetings,
        icon: BadgeCheck,
        iconClassName: "text-emerald-400",
      },
    ];
  }, [display.totalChats, display.totalMeetings]);

  return (
    <div className="min-h-full bg-[#0f0f0f]">
      <div className="mb-8 flex items-center gap-4">
        <h1 className="text-3xl font-semibold text-white">Dashboard Overview</h1>
        <button
          type="button"
          onClick={() => void fetchData()}
          title="Refresh data"
          className="rounded-lg border border-white/10 bg-white/5 p-2 text-zinc-400 transition hover:bg-white/10 hover:text-white"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      </div>

      {isLoading ? (
        <DashboardSkeleton />
      ) : (
        <div className="space-y-8">
          {error ? (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              {error}
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {statsList.map((stat) => {
              const Icon = stat.icon;

              return (
                <div
                  key={stat.label}
                  className="rounded-2xl border-l-4 border-l-[#7c3aed] bg-[#1a1a1a] p-5 shadow-lg shadow-black/10"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm text-zinc-400">{stat.label}</p>
                      <p className="mt-3 text-3xl font-semibold text-white">
                        {stat.value}
                      </p>
                    </div>
                    <div className="rounded-xl bg-white/5 p-3">
                      <Icon className={`h-5 w-5 ${stat.iconClassName}`} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <section className="overflow-hidden rounded-2xl bg-[#1a1a1a] shadow-lg shadow-black/10">
            <div className="border-b border-white/5 px-6 py-4">
              <h2 className="text-lg font-semibold text-white">Recent Leads</h2>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-white/5">
                <thead className="bg-white/[0.02]">
                  <tr className="text-left text-xs uppercase tracking-[0.18em] text-zinc-500">
                    <th className="px-6 py-4 font-medium">Name</th>
                    <th className="px-6 py-4 font-medium">Email</th>
                    <th className="px-6 py-4 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {recentLeads.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-6 py-12 text-center text-sm text-zinc-400">
                        No leads yet. Start chatting to capture leads.
                      </td>
                    </tr>
                  ) : recentLeads.map((lead, index) => (
                    <tr key={`${lead.name}-${lead.created_at}-${index}`}>
                      <td className="px-6 py-4 text-sm font-medium text-white">
                        {lead?.name ?? "Unknown"}
                      </td>
                      <td className="px-6 py-4 text-sm text-zinc-300">
                        {lead?.email ?? "N/A"}
                      </td>
                      <td className="px-6 py-4 text-sm text-zinc-400">
                        {formatDate(lead?.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
