"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RotateCcw } from "lucide-react";

import { adminGet } from "@/lib/apiClient";

type CalendarStatus = "confirmed" | "pending" | "cancelled";

interface Meeting {
  id?: string;
  user_name?: string | null;
  user_email?: string | null;
  purpose?: string | null;
  preferred_time?: string | null;
  calendar_status?: CalendarStatus | null;
  created_at?: string | null;
  meet_link?: string | null;
}

const STATUS_CONFIG: Record<
  CalendarStatus,
  { label: string; className: string }
> = {
  confirmed: {
    label: "✅ Confirmed",
    className: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/20",
  },
  pending: {
    label: "⏳ Pending",
    className: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/20",
  },
  cancelled: {
    label: "❌ Cancelled",
    className: "bg-red-500/15 text-red-300 ring-1 ring-red-500/20",
  },
};

const endpointCandidates = [
  "/api/v1/admin/meetings",
  "/api/v1/admin/bookings",
];

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return "Not scheduled";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
};

const getStatusMeta = (status?: string | null) =>
  STATUS_CONFIG[(status as CalendarStatus) || "pending"] ?? {
    label: "⏳ Pending",
    className: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/20",
  };

const extractMeetings = (payload: unknown): Meeting[] => {
  if (Array.isArray(payload)) {
    return payload as Meeting[];
  }

  if (!payload || typeof payload !== "object") {
    return [];
  }

  const record = payload as Record<string, unknown>;
  const candidates = [record.data, record.meetings, record.bookings, record.items];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate as Meeting[];
    }
  }

  if (record.data && typeof record.data === "object") {
    const nested = record.data as Record<string, unknown>;
    const nestedCandidates = [nested.meetings, nested.bookings, nested.items];

    for (const candidate of nestedCandidates) {
      if (Array.isArray(candidate)) {
        return candidate as Meeting[];
      }
    }
  }

  return [];
};

const LoadingState = () => {
  return (
    <div className="grid min-h-[70vh] gap-6 lg:grid-cols-[30%_70%]">
      <div className="rounded-2xl border border-white/5 bg-[#1a1a1a] p-4">
        <div className="h-11 animate-pulse rounded-xl bg-white/5" />
        <div className="mt-4 space-y-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <div
              key={index}
              className="h-24 animate-pulse rounded-xl bg-white/5"
            />
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-white/5 bg-[#1a1a1a] p-6">
        <div className="h-8 w-56 animate-pulse rounded bg-white/10" />
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="h-20 animate-pulse rounded-2xl bg-white/5"
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMeetings = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      let payload: unknown = null;

      for (const endpoint of endpointCandidates) {
        try {
          payload = await adminGet<unknown>(endpoint);
          console.log("API RESPONSE:", payload);
          break;
        } catch (err) {
          const message = err instanceof Error ? err.message : "";

          if (!message.includes("404")) {
            throw err;
          }
        }
      }

      const items = extractMeetings(payload);
      setMeetings(items);
      setSelectedMeeting(items[0] ?? null);
    } catch (err) {
      console.error("Meetings error:", err);
      setMeetings([]);
      setSelectedMeeting(null);
      setError(err instanceof Error ? err.message : "Failed to load meetings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchMeetings();
  }, [fetchMeetings]);

  const filteredMeetings = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return meetings;
    }

    return meetings.filter((meeting) => {
      const name = meeting?.user_name?.toLowerCase() ?? "";
      const email = meeting?.user_email?.toLowerCase() ?? "";
      const purpose = meeting?.purpose?.toLowerCase() ?? "";

      return (
        name.includes(query) || email.includes(query) || purpose.includes(query)
      );
    });
  }, [meetings, search]);

  return (
    <div className="min-h-full bg-[#0f0f0f]">
      <div className="mb-8 flex items-center gap-4">
        <h1 className="text-3xl font-semibold text-white">Meeting Requests</h1>
        <button
          type="button"
          onClick={() => void fetchMeetings()}
          title="Refresh meetings"
          className="rounded-lg border border-white/10 bg-white/5 p-2 text-zinc-400 transition hover:bg-white/10 hover:text-white"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      </div>

      {loading ? (
        <LoadingState />
      ) : (
        <div className="grid min-h-[70vh] gap-6 lg:grid-cols-[30%_70%]">
          <aside className="rounded-2xl border border-white/5 bg-[#1a1a1a] p-4 shadow-lg shadow-black/10">
            <div className="mb-3">
              <input
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search meetings"
                className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition placeholder:text-zinc-500 focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
              />
            </div>

            {error ? (
              <div className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                {error}
              </div>
            ) : null}

            <div className="space-y-3 overflow-y-auto pr-1">
              {filteredMeetings.length === 0 ? (
                <div className="rounded-xl border border-white/5 bg-white/[0.02] px-4 py-8 text-center text-sm text-zinc-400">
                  No meetings booked yet.
                </div>
              ) : (
                filteredMeetings.map((meeting, index) => {
                  const isSelected =
                    (meeting?.id ?? `meeting-${index}`) ===
                    (selectedMeeting?.id ?? "selected");
                  const statusMeta = getStatusMeta(meeting?.calendar_status);

                  return (
                    <button
                      key={meeting?.id ?? `meeting-${index}`}
                      type="button"
                      onClick={() => setSelectedMeeting(meeting)}
                      className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                        isSelected
                          ? "border-[#7c3aed] bg-[#7c3aed]/15 shadow-[0_0_0_1px_rgba(124,58,237,0.35)]"
                          : "border-white/5 bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-white">
                            {meeting?.user_name ?? "Unknown"}
                          </p>
                          <p className="mt-1 text-xs text-zinc-500">
                            {meeting?.user_email ?? "No email provided"}
                          </p>
                        </div>
                        <span
                          className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-medium ${statusMeta.className}`}
                        >
                          {statusMeta.label}
                        </span>
                      </div>

                      <p className="mt-3 text-xs text-zinc-400">
                        {meeting?.purpose ?? "No purpose provided"}
                      </p>
                    </button>
                  );
                })
              )}
            </div>
          </aside>

          <section className="rounded-2xl border border-white/5 bg-[#1a1a1a] p-6 shadow-lg shadow-black/10">
            {selectedMeeting ? (
              <div className="flex h-full flex-col">
                <div className="border-b border-white/5 pb-6">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div>
                      <h2 className="text-2xl font-semibold text-white">
                        {selectedMeeting?.user_name ?? "Unknown"}
                      </h2>
                      <p className="mt-2 text-sm text-zinc-400">
                        {selectedMeeting?.user_email ?? "No email provided"}
                      </p>
                    </div>
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${getStatusMeta(selectedMeeting?.calendar_status).className}`}
                    >
                      {getStatusMeta(selectedMeeting?.calendar_status).label}
                    </span>
                  </div>

                  <div className="mt-6 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl bg-white/[0.03] px-4 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">
                        Purpose
                      </p>
                      <p className="mt-2 text-sm text-zinc-200">
                        {selectedMeeting?.purpose ?? "Not provided"}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-white/[0.03] px-4 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">
                        Preferred Time
                      </p>
                      <p className="mt-2 text-sm text-zinc-200">
                        {formatDateTime(selectedMeeting?.preferred_time)}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-white/[0.03] px-4 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">
                        Requested At
                      </p>
                      <p className="mt-2 text-sm text-zinc-200">
                        {formatDateTime(selectedMeeting?.created_at)}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-white/[0.03] px-4 py-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">
                        Meeting Link
                      </p>
                      {selectedMeeting?.meet_link ? (
                        <a
                          href={selectedMeeting.meet_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-2 inline-block text-sm text-violet-300 underline underline-offset-4"
                        >
                          Join meeting
                        </a>
                      ) : (
                        <p className="mt-2 text-sm text-zinc-500">Not available</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-[50vh] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] text-sm text-zinc-400">
                Select a meeting request to view details
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
