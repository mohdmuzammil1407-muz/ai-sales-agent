"use client";

import { AxiosError } from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Mail, Pencil, RotateCcw, Trash2 } from "lucide-react";

import { sendFollowupEmail } from "@/lib/api";
import {
  adminDelete,
  adminPut,
  loadAdminConversations,
  removeLeadOverride,
  saveLeadOverride,
} from "@/lib/apiHelper";

type Lead = {
  id: string;
  name: string;
  email: string;
  phone?: string;
  whatsapp_number?: string;
  recommended_package?: string;
  order_confirmed?: boolean;
  order_intent?: boolean;
  order_ref?: string;
  created_at?: string;
};

interface LeadRecord extends Omit<Lead, "id" | "created_at"> {
  id?: string;
  conversation_id: string;
  created_at?: string;
}

type EditFormState = {
  name: string;
  email: string;
  phone: string;
};

const normalizeLead = (lead: Lead, index: number): LeadRecord => {
  const record = lead as Lead & {
    conversation_id?: string;
  };

  return {
    ...lead,
    conversation_id: record.conversation_id || lead.id || `lead-${index + 1}`,
  };
};

const LoadingSkeleton = () => {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            key={index}
            className="h-12 animate-pulse rounded-xl bg-white/5"
          />
        ))}
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/5 bg-[#1a1a1a]">
        <div className="border-b border-white/5 px-6 py-4">
          <div className="h-5 w-40 animate-pulse rounded bg-white/10" />
        </div>
        <div className="space-y-3 p-6">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-14 animate-pulse rounded-xl bg-white/5"
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default function LeadsPage() {
  const router = useRouter();
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [editingLead, setEditingLead] = useState<LeadRecord | null>(null);
  const [editForm, setEditForm] = useState<EditFormState>({
    name: "",
    email: "",
    phone: "",
  });
  const [savingLead, setSavingLead] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const normalizedLeads = (
        await loadAdminConversations<Lead>("/api/v1/admin/leads")
      ).map(normalizeLead);
      console.log("API RESPONSE:", normalizedLeads);
      setLeads(normalizedLeads);
    } catch (err: unknown) {
      console.error("Leads error:", err);
      setError(err instanceof Error ? err.message : "Unable to load leads");
      setLeads([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLeads();
  }, [loadLeads]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setToast(null);
    }, 3000);

    return () => window.clearTimeout(timeout);
  }, [toast]);

  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      const leadName = lead.name || "Anonymous";
      const leadEmail = lead.email || "";

      const matchesSearch =
        search.trim() === "" ||
        leadName.toLowerCase().includes(search.toLowerCase()) ||
        leadEmail.toLowerCase().includes(search.toLowerCase());

      return matchesSearch;
    });
  }, [leads, search]);

  const resetFilters = () => {
    setSearch("");
  };

  const handleViewChat = (conversationId: string) => {
    router.push(`/dashboard/chats?id=${conversationId}`);
  };

  const handleSendEmail = async (lead: LeadRecord) => {
    const leadId = lead.id || lead.conversation_id;

    try {
      setSendingId(leadId);
      setError(null);
      await sendFollowupEmail(leadId, "followup");
    } catch {
      setError(`Unable to send follow-up email to ${lead.name || "this lead"}.`);
    } finally {
      setSendingId(null);
    }
  };

  const handleOpenEdit = (lead: LeadRecord) => {
    setEditingLead(lead);
    setEditForm({
      name: lead.name || "",
      email: lead.email || "",
      phone: lead.phone || "",
    });
  };

  const handleCloseEdit = () => {
    setEditingLead(null);
    setEditForm({
      name: "",
      email: "",
      phone: "",
    });
  };

  const handleSaveEdit = async () => {
    if (!editingLead?.conversation_id) {
      return;
    }

    const conversationId = editingLead.conversation_id;
    const nextLead = {
      ...editingLead,
      ...editForm,
    };

    try {
      setSavingLead(true);
      setError(null);
      setToast(null);

      saveLeadOverride(conversationId, {
        name: nextLead.name,
        email: nextLead.email,
        phone: nextLead.phone,
      });

      setLeads((prev) =>
        prev.map((lead) =>
          lead.conversation_id === conversationId
            ? nextLead
            : lead
        )
      );

      try {
        await adminPut(`/api/v1/admin/conversations/${conversationId}`, {
          name: nextLead.name,
          email: nextLead.email,
          phone: nextLead.phone,
        });
        setToast("Lead details updated.");
      } catch (err) {
        const error = err as AxiosError;
        if (error.response?.status === 404) {
          setToast("Lead details updated locally.");
        } else {
          setError("Saved locally. Server sync is unavailable right now.");
        }
      }

      handleCloseEdit();
    } catch (err) {
      console.error("Lead update error:", err);
      setError("Unable to update this lead right now.");
    } finally {
      setSavingLead(false);
    }
  };

  const handleDeleteLead = async (lead: LeadRecord) => {
    const leadId = lead.id || lead.conversation_id;

    if (!window.confirm(`Delete ${lead.name || "this lead"}?`)) {
      return;
    }

    try {
      setDeletingId(leadId);
      setError(null);
      setToast(null);
      await adminDelete(`/api/v1/admin/conversations/${lead.conversation_id}`);
      setLeads((prev) =>
        prev.filter((item) => item.conversation_id !== lead.conversation_id)
      );
      removeLeadOverride(lead.conversation_id);
    } catch (err) {
      console.error("Lead delete error:", err);
      setError(`Unable to delete ${lead.name || "this lead"}.`);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="min-h-full bg-[#0f0f0f]">
      <div className="mb-8 flex flex-col gap-2">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-semibold text-white">Leads</h1>
          <button
            type="button"
            onClick={() => void loadLeads()}
            title="Refresh leads"
            className="rounded-lg border border-white/10 bg-white/5 p-2 text-zinc-400 transition hover:bg-white/10 hover:text-white"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
        <p className="text-sm text-zinc-400">
          All Leads
        </p>
      </div>

      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-6">
          {toast ? (
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
              {toast}
            </div>
          ) : null}

          {error ? (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              <div className="flex items-center justify-between gap-4">
                <span>{error}</span>
                <button
                  type="button"
                  onClick={() => void loadLeads()}
                  className="rounded-lg border border-amber-300/20 px-3 py-1 text-xs font-medium text-amber-100 transition hover:bg-amber-400/10"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : null}

          <div className="grid gap-4 rounded-2xl border border-white/5 bg-[#1a1a1a] p-4 lg:grid-cols-[1fr_auto]">
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name or email"
              className="rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition placeholder:text-zinc-500 focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
            />

            <button
              type="button"
              onClick={resetFilters}
              className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-zinc-200 transition hover:bg-white/10 hover:text-white"
            >
              Reset Filters
            </button>
          </div>

          <div className="overflow-hidden rounded-2xl border border-white/5 bg-[#1a1a1a] shadow-lg shadow-black/10">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-white/5">
                <thead className="bg-white/[0.02]">
                  <tr className="text-left text-xs uppercase tracking-[0.18em] text-zinc-500">
                    <th className="px-6 py-4 font-medium">Name</th>
                    <th className="px-6 py-4 font-medium">Reference</th>
                    <th className="px-6 py-4 font-medium">Email</th>
                    <th className="px-6 py-4 font-medium">Package</th>
                    <th className="px-6 py-4 font-medium">WhatsApp</th>
                    <th className="px-6 py-4 font-medium">Phone</th>
                    <th className="px-6 py-4 font-medium">Date</th>
                    <th className="px-6 py-4 font-medium text-right">Actions</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-white/5">
                  {filteredLeads.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-6 py-12 text-center text-sm text-zinc-400"
                      >
                        No leads found.
                      </td>
                    </tr>
                  ) : (
                    filteredLeads.map((lead) => {
                      const actionId = lead.id || lead.conversation_id;
                      const leadName = lead?.name ?? "Unknown";
                      const leadEmail = lead?.email ?? "N/A";
                      const leadPhone = lead?.phone ?? "N/A";
                      const leadDate = lead.created_at ? new Date(lead.created_at).toLocaleDateString() : "--";

                      return (
                        <tr key={actionId}>
                          <td className="px-6 py-4 text-sm font-medium text-white">
                            <div className="flex items-center gap-2">
                              {leadName}
                              {lead.order_intent && (
                                <span className="inline-flex items-center gap-1 rounded bg-orange-500/10 px-1.5 py-0.5 text-[10px] font-medium text-orange-400">
                                  🔥 Order Intent
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm font-medium text-purple-400">
                            {lead.order_ref ?? "—"}
                          </td>
                          <td className="px-6 py-4 text-sm text-zinc-300">
                            {leadEmail}
                          </td>
                          <td className="px-6 py-4 text-sm text-zinc-300">
                            {lead.recommended_package ?? "—"}
                          </td>
                          <td className="px-6 py-4 text-sm text-zinc-300">
                            {lead.whatsapp_number ?? "—"}
                          </td>
                          <td className="px-6 py-4 text-sm text-zinc-300">
                            {leadPhone}
                          </td>
                          <td className="px-6 py-4 text-sm text-zinc-400">
                            {leadDate}
                          </td>
                          <td className="px-6 py-4 text-sm">
                            <div className="flex w-[172px] ml-auto items-center justify-end gap-1.5">
                              <button
                                type="button"
                                onClick={() => handleOpenEdit(lead)}
                                className="rounded-lg border border-white/10 bg-white/5 p-2 text-gray-400 transition hover:border-purple-500/30 hover:bg-purple-500/10 hover:text-purple-300"
                                title="Edit lead"
                              >
                                <Pencil className="h-4 w-4" />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  handleViewChat(lead.conversation_id)
                                }
                                className="rounded-lg bg-[#7c3aed] px-3 py-2 text-xs font-medium text-white transition hover:bg-[#8b5cf6] whitespace-nowrap"
                              >
                                View Chat
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleSendEmail(lead)}
                                disabled={sendingId === actionId}
                                className="rounded-lg border border-white/10 bg-white/5 p-2 text-gray-400 transition hover:border-white/15 hover:bg-white/10 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
                                title="Send email"
                              >
                                {sendingId === actionId ? (
                                  "..."
                                ) : (
                                  <Mail className="h-4 w-4" />
                                )}
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleDeleteLead(lead)}
                                disabled={deletingId === actionId}
                                className="rounded-lg border border-red-500/20 bg-red-500/10 p-2 text-red-400 transition hover:bg-red-500/20 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-60"
                                title="Delete lead"
                              >
                                {deletingId === actionId ? (
                                  "..."
                                ) : (
                                  <Trash2 className="h-4 w-4" />
                                )}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {editingLead ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#1a1a1a] p-6 shadow-2xl shadow-black/40">
            <h2 className="text-xl font-semibold text-white">Edit Lead</h2>

            <div className="mt-6 space-y-4">
              <input
                type="text"
                value={editForm.name}
                onChange={(event) =>
                  setEditForm((prev) => ({
                    ...prev,
                    name: event.target.value,
                  }))
                }
                placeholder="Name"
                className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition placeholder:text-zinc-500 focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
              />
              <input
                type="email"
                value={editForm.email}
                onChange={(event) =>
                  setEditForm((prev) => ({
                    ...prev,
                    email: event.target.value,
                  }))
                }
                placeholder="Email"
                className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition placeholder:text-zinc-500 focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
              />
              <input
                type="tel"
                value={editForm.phone}
                onChange={(event) =>
                  setEditForm((prev) => ({
                    ...prev,
                    phone: event.target.value,
                  }))
                }
                placeholder="Phone"
                className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition placeholder:text-zinc-500 focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
              />
            </div>

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={handleCloseEdit}
                disabled={savingLead}
                className="rounded-xl bg-[#2a2a2a] px-4 py-3 text-sm font-medium text-zinc-200 transition hover:bg-[#333333] disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleSaveEdit()}
                disabled={savingLead}
                className="rounded-xl bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 px-5 py-3 text-sm font-semibold text-white transition hover:from-violet-500 hover:via-purple-500 hover:to-fuchsia-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {savingLead ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
