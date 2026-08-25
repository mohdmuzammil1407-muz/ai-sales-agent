"use client";

import { useEffect, useMemo, useState } from "react";
import { BadgeCheck, Clock3, Mail } from "lucide-react";

import { sendFollowupEmail } from "@/lib/api";
import { loadAdminConversations } from "@/lib/apiHelper";

type Lead = {
  id: string;
  name: string;
  email: string;
  business_name: string;
  recommended_package: string;
  budget: number;
  lead_score: number;
  order_confirmed: boolean;
  video_type?: string;
  created_at?: string;
};

type EmailType = "followup" | "price_offer" | "reminder";

type LeadRecord = Lead & {
  conversation_id?: string;
};

interface EmailHistoryItem {
  name: string;
  type: EmailType;
  status: string;
  sent_at: string;
}

const emailTypeOptions: Array<{ value: EmailType; label: string }> = [
  { value: "followup", label: "General Follow-up" },
  { value: "price_offer", label: "Special Price Offer" },
  { value: "reminder", label: "Project Reminder" },
];

const formatEmailType = (type: EmailType) => {
  if (type === "price_offer") {
    return "Special Price Offer";
  }

  if (type === "followup") {
    return "General Follow-up";
  }

  return "Project Reminder";
};

const buildPreview = (lead: LeadRecord | null, emailType: EmailType) => {
  const name = lead?.name || "there";
  const selectedPackage = lead?.recommended_package || "selected";

  if (emailType === "price_offer") {
    return `Hi ${name}, we have a special offer for you!
Get 10% off on the ${selectedPackage} package if you confirm today.
This offer expires in 48 hours.`;
  }

  if (emailType === "reminder") {
    return `Hi ${name}, just a friendly reminder about your video project.
Your selected package ${selectedPackage} is ready to start.
Shall we begin?`;
  }

  return `Hi ${name}, following up on your interest in our video services.
We noticed you were looking at our ${selectedPackage} package.
Would you like to proceed or discuss further?`;
};

const LoadingSkeleton = () => {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
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

      <div className="rounded-2xl bg-[#1a1a1a] p-6">
        <div className="h-6 w-52 animate-pulse rounded bg-white/10" />
        <div className="mt-6 grid gap-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="h-12 animate-pulse rounded-xl bg-white/5"
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default function EmailsPage() {
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [emailHistory] = useState<EmailHistoryItem[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState("");
  const [emailType, setEmailType] = useState<EmailType>("followup");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState("");

  useEffect(() => {
    const loadLeads = async () => {
      setLoading(true);
      setError(null);

      try {
        const normalized = await loadAdminConversations<LeadRecord>("/api/v1/admin/leads");
        console.log("API RESPONSE:", normalized);

        if (normalized.length === 0) {
          setLeads([]);
          setSelectedLeadId("");
        } else {
          setLeads(normalized);
          setSelectedLeadId(normalized[0]?.id || normalized[0]?.conversation_id || "");
        }
      } catch (err: unknown) {
        console.error("Emails error:", err);
        setLeads([]);
        setSelectedLeadId("");
        setError("Unable to load live leads.");
      } finally {
        setLoading(false);
      }
    };

    void loadLeads();
  }, []);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setToast("");
    }, 3000);

    return () => window.clearTimeout(timeout);
  }, [toast]);

  const selectedLead =
    leads.find((lead) => (lead.id || lead.conversation_id) === selectedLeadId) ?? null;

  const previewText = useMemo(
    () => buildPreview(selectedLead, emailType),
    [emailType, selectedLead]
  );

  const stats = useMemo(() => {
    const emailsSentToday = emailHistory.filter(
      (entry) => entry.sent_at === new Date().toISOString().split('T')[0]
    ).length;
    const followupsPending = leads.filter((lead) => !lead.order_confirmed).length;
    const priceOffersSent = emailHistory.filter(
      (entry) => entry.type === "price_offer"
    ).length;

    return [
      {
        label: "Emails Sent Today",
        value: emailsSentToday,
        icon: Mail,
        iconClassName: "text-sky-400",
      },
      {
        label: "Follow-ups Pending",
        value: followupsPending,
        icon: Clock3,
        iconClassName: "text-amber-400",
      },
      {
        label: "Price Offers Sent",
        value: priceOffersSent,
        icon: BadgeCheck,
        iconClassName: "text-emerald-400",
      },
    ];
  }, [emailHistory, leads]);

  const handleSend = async () => {
    if (!selectedLead) {
      setError("Please select a lead before sending an email.");
      return;
    }

    try {
      setSending(true);
      setError("");
      await sendFollowupEmail(selectedLead.id || selectedLead.conversation_id || "", emailType);
      setToast("Email sent successfully.");
    } catch {
      setError("Unable to send email right now. Please try again.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-full bg-[#0f0f0f]">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-white">Email Campaigns</h1>
      </div>

      {toast ? (
        <div className="mb-6 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          {toast}
        </div>
      ) : null}

      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          {error ? (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              {error}
            </div>
          ) : null}

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {stats.map((stat) => {
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
          </section>

          <section className="rounded-2xl bg-[#1a1a1a] p-6 shadow-lg shadow-black/10">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-white">
                Send Follow-up Email
              </h2>
            </div>

            <div className="grid gap-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-zinc-200">
                  Lead
                </label>
                <select
                  value={selectedLeadId}
                  suppressHydrationWarning={true}
                  onChange={(event) => setSelectedLeadId(event.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
                >
                  {leads.map((lead) => (
                    <option key={lead.id || lead.conversation_id} value={lead.id || lead.conversation_id!}>
                      {lead.name} - {lead.business_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-zinc-200">
                  Email Type
                </label>
                <select
                  value={emailType}
                  suppressHydrationWarning={true}
                  onChange={(event) =>
                    setEmailType(event.target.value as EmailType)
                  }
                  className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
                >
                  {emailTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-zinc-200">
                  Preview
                </label>
                <textarea
                  value={previewText}
                  readOnly
                  suppressHydrationWarning={true}
                  rows={6}
                  className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm leading-6 text-zinc-200 outline-none"
                />
              </div>

              <div>
                <button
                  type="button"
                  onClick={() => void handleSend()}
                  disabled={sending}
                  className="rounded-xl bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 px-5 py-3 text-sm font-semibold text-white transition hover:from-violet-500 hover:via-purple-500 hover:to-fuchsia-500 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {sending ? "Sending..." : "Send Email"}
                </button>
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl bg-[#1a1a1a] shadow-lg shadow-black/10">
            <div className="border-b border-white/5 px-6 py-4">
              <h2 className="text-lg font-semibold text-white">Email History</h2>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-white/5">
                <thead className="bg-white/[0.02]">
                  <tr className="text-left text-xs uppercase tracking-[0.18em] text-zinc-500">
                    <th className="px-6 py-4 font-medium">Lead Name</th>
                    <th className="px-6 py-4 font-medium">Email Type</th>
                    <th className="px-6 py-4 font-medium">Status</th>
                    <th className="px-6 py-4 font-medium">Sent At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {emailHistory.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-6 py-12 text-center text-sm text-zinc-400">
                        No emails sent yet
                      </td>
                    </tr>
                  ) : emailHistory.map((item, index) => (
                    <tr key={`${item.name}-${index}`}>
                      <td className="px-6 py-4 text-sm font-medium text-white">
                        {item.name}
                      </td>
                      <td className="px-6 py-4 text-sm text-zinc-300">
                        {formatEmailType(item.type)}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <span className="inline-flex rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-300 ring-1 ring-emerald-500/20">
                          {item.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-zinc-400">
                        {item.sent_at}
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
