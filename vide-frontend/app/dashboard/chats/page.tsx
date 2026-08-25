"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { RotateCcw, Trash2 } from "lucide-react";

import {
  adminDelete,
  adminGet,
  applyLeadOverride,
  loadAdminConversations,
} from "@/lib/apiHelper";

type Message = {
  role: string;
  content: string;
  timestamp?: string;
  type?: string;
};

type ConversationRecord = {
  conversation_id: string;
  stage: string;
  lead_score: number;
  messages: Message[];
  created_at?: string;
  name?: string | null;
  email?: string | null;
  business_name?: string | null;
  recommended_package?: string | null;
  sales_mode?: string | null;
  order_confirmed?: boolean;
  message_count?: number;
};

const getStageBadgeClass = (stage: string) => {
  const stageKey = stage.toLowerCase();

  if (stageKey === "post_sale" || stageKey === "closing") {
    return "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/20";
  }

  if (stageKey === "qualification" || stageKey === "recommendation") {
    return "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/20";
  }

  return "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/20";
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

const normalizeConversation = (
  conversation: Partial<ConversationRecord>,
  index: number
): ConversationRecord => {
  const record = conversation as ConversationRecord;

  return {
    ...record,
    name: record.name ?? null,
    email: record.email ?? null,
    business_name: record.business_name ?? null,
    recommended_package: record.recommended_package ?? null,
    sales_mode: record.sales_mode ?? "standard",
    order_confirmed: record.order_confirmed ?? false,
    message_count: record.message_count ?? (record.messages?.length || 0),
    messages: record.messages ?? [],
    created_at: record.created_at ?? `mock-${index}`,
  };
};

const LoadingState = () => {
  return (
    <div className="grid min-h-[70vh] gap-6 lg:grid-cols-[30%_70%]">
      <div className="rounded-2xl border border-white/5 bg-[#1a1a1a] p-4">
        <div className="h-11 animate-pulse rounded-xl bg-white/5" />
        <div className="mt-4 space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-24 animate-pulse rounded-xl bg-white/5"
            />
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-white/5 bg-[#1a1a1a] p-6">
        <div className="h-8 w-56 animate-pulse rounded bg-white/10" />
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="h-20 animate-pulse rounded-2xl bg-white/5"
            />
          ))}
        </div>
        <div className="mt-6 space-y-4">
          {Array.from({ length: 5 }).map((_, index) => (
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

export default function ChatsPage() {
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [selectedConv, setSelectedConv] = useState<ConversationRecord | null>(
    null
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollChatToBottom = useCallback(() => {
    window.setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, 100);
  }, []);

  const handleSelectConversation = useCallback(async (conv: ConversationRecord) => {
    setSelectedConv(conv);
    setChatError(null);
    setMessages([]);
    setLoadingMessages(true);

    try {
      const data = await adminGet<Record<string, unknown>>(`/api/v1/admin/chats/${conv.conversation_id}`);
      console.log("=== RAW API RESPONSE ===", data);
      console.log("CHAT DETAIL RESPONSE:", data);
      const rawMessages = data.messages;
      console.log("=== MESSAGES RECEIVED ===", rawMessages);
      console.log("=== MESSAGE COUNT ===", Array.isArray(rawMessages) ? rawMessages.length : undefined);
      console.log("MESSAGES ARRAY:", rawMessages);
      const nextMessages = Array.isArray(rawMessages) ? (rawMessages as Message[]) : [];
      setMessages(nextMessages);
      scrollChatToBottom();
      setSelectedConv((prev) => {
        const merged = applyLeadOverride(data);
        return {
          ...prev!,
          ...merged,
          email:
            (typeof merged.email === "string" && merged.email.trim().length > 0
              ? merged.email
              : prev?.email) ?? null,
          business_name:
            (typeof merged.business_name === "string" &&
            merged.business_name.trim().length > 0
              ? merged.business_name
              : prev?.business_name) ?? null,
          name:
            (typeof merged.name === "string" && merged.name.trim().length > 0
              ? merged.name
              : prev?.name) ?? null,
          recommended_package:
            (typeof merged.recommended_package === "string" &&
            merged.recommended_package.trim().length > 0
              ? merged.recommended_package
              : prev?.recommended_package) ?? null,
          messages: nextMessages,
          message_count: nextMessages.length,
        };
      });
    } catch (err) {
      console.error("Messages error:", err);
      setChatError(err instanceof Error ? err.message : "Failed to load chat.");
    } finally {
      setLoadingMessages(false);
    }
  }, [scrollChatToBottom]);

  const refreshConversations = useCallback(async (preferredConversationId?: string) => {
    setLoading(true);
    setError(null);

    try {
      const normalizedData = (await loadAdminConversations<ConversationRecord>())
        .map(normalizeConversation);
      console.log("API RESPONSE:", normalizedData);

      if (normalizedData.length === 0) {
        setConversations([]);
        setSelectedConv(null);
        setMessages([]);
        setError(null);
        return;
      }

      setConversations(normalizedData);

      const queryId = preferredConversationId || searchParams.get("id");
      const nextConversation =
        (queryId &&
          normalizedData.find(
            (conversation) => conversation.conversation_id === queryId
          )) ||
        normalizedData[0];

      if (nextConversation) {
        await handleSelectConversation(nextConversation);
      }
    } catch (err) {
      console.error("Conversations error:", err);
      setConversations([]);
      setError("Unable to load live conversations.");
    } finally {
      setLoading(false);
    }
  }, [handleSelectConversation, searchParams]);

  const handleDeleteConversation = async (conv: ConversationRecord) => {
    if (!window.confirm("Delete this conversation?")) return;
    setDeletingId(conv.conversation_id);
    try {
      await adminDelete(`/api/v1/admin/conversations/${conv.conversation_id}`);
      setConversations((prev) =>
        prev.filter((c) => c.conversation_id !== conv.conversation_id)
      );
      if (selectedConv?.conversation_id === conv.conversation_id) {
        setSelectedConv(null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Delete error:", err);
      setError("Failed to delete conversation. Please try again.");
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    console.log("STATE messages:", messages);
  }, [messages]);

  const filteredConversations = useMemo(() => {
    return conversations.filter((conversation) => {
      const name = conversation?.name ?? "Anonymous";
      const email = conversation?.email ?? "";
      const business = conversation?.business_name ?? "";
      const query = search.trim().toLowerCase();

      if (!query) {
        return true;
      }

      return (
        name.toLowerCase().includes(query) ||
        email.toLowerCase().includes(query) ||
        business.toLowerCase().includes(query)
      );
    });
  }, [conversations, search]);

  console.log("RENDERING MESSAGES COUNT:", messages.length);
  console.log("RENDER COUNT:", messages.length);

  return (
    <div suppressHydrationWarning={true} className="min-h-full bg-[#0f0f0f]">
      <div className="mb-8 flex items-center gap-4">
        <h1 className="text-3xl font-semibold text-white">Conversations</h1>
        <button
          type="button"
          onClick={() => {
            void refreshConversations(selectedConv?.conversation_id);
          }}
          title="Refresh conversations"
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
                placeholder="Search conversations"
                className="w-full rounded-xl border border-white/10 bg-[#111111] px-4 py-3 text-sm text-white outline-none transition placeholder:text-zinc-500 focus:border-[#7c3aed] focus:ring-2 focus:ring-[#7c3aed]/30"
              />
            </div>


            {error ? (
              <div className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                {error}
              </div>
            ) : null}

            <div className="space-y-3 overflow-y-auto pr-1">
              {filteredConversations.length === 0 ? (
                <div className="rounded-xl border border-white/5 bg-white/[0.02] px-4 py-8 text-center text-sm text-zinc-400">
                  No conversations yet.
                </div>
              ) : (
                filteredConversations.map((conversation) => {
                  const isSelected =
                    conversation.conversation_id ===
                    selectedConv?.conversation_id;
                  const isDeleting = deletingId === conversation.conversation_id;

                  return (
                    <div key={conversation.conversation_id} className="relative">
                      <button
                        type="button"
                        onClick={() => void handleSelectConversation(conversation)}
                        className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                          isSelected
                            ? "border-[#7c3aed] bg-[#7c3aed]/15 shadow-[0_0_0_1px_rgba(124,58,237,0.35)]"
                            : "border-white/5 bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3 pr-6">
                          <div>
                            <p className="text-sm font-semibold text-white">
                              {conversation?.name ?? "Unknown User"}
                            </p>
                            <p className="mt-1 text-xs text-zinc-500">
                              {conversation.message_count ?? 0} messages
                            </p>
                          </div>
                          <span className="text-xs text-zinc-500">
                            {conversation.created_at ? new Date(conversation.created_at).toLocaleString() : "--"}
                          </span>
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDeleteConversation(conversation);
                        }}
                        disabled={isDeleting}
                        title="Delete conversation"
                        className="absolute right-3 top-3 rounded-lg p-2 text-red-400 bg-red-500/10 border border-red-500/20 transition hover:bg-red-500/20 hover:text-red-300 disabled:opacity-40"
                      >
                        {isDeleting ? (
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-red-400/30 border-t-red-400" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </aside>

          <section className="rounded-2xl border border-white/5 bg-[#1a1a1a] p-6 shadow-lg shadow-black/10">
            {selectedConv ? (
              <div className="flex h-full flex-col">
                <div className="border-b border-white/5 pb-6">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div>
                      <h2 className="text-2xl font-semibold text-white">
                        {selectedConv?.name ?? "Unknown User"}
                      </h2>
                      <div className="mt-2 flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4 text-sm text-zinc-400">
                        {selectedConv?.email && (
                          <span>{selectedConv.email}</span>
                        )}
                        {selectedConv?.email && selectedConv?.created_at && (
                          <span className="hidden sm:inline">&bull;</span>
                        )}
                        {selectedConv?.created_at && (
                          <span>
                            {new Date(selectedConv.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex-1 space-y-4 overflow-y-auto pr-1">
                  <div className="flex flex-col gap-3 p-4 overflow-y-auto max-h-[500px] bg-[#0f0f0f] rounded-xl">
                    {messages.length === 0 ? (
                      <div className="flex items-center justify-center h-40 text-gray-600 text-sm">
                        No messages in this conversation yet.
                      </div>
                    ) : (
                      messages.map((msg: Message, i: number) => {
                        const roleGroup = msg.role?.toLowerCase?.() === "assistant" ? "assistant" : "user";
                        return (
                          <div
                            key={i}
                            className={`flex flex-col max-w-[75%] gap-1 ${
                              roleGroup === "user" ? "self-end items-end" : "self-start items-start"
                            }`}
                          >
                            <span className="text-xs text-gray-500 uppercase tracking-wide px-1">
                              {roleGroup === "user" ? "User" : "Vidio"}
                            </span>
                            <div
                              className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                                roleGroup === "user"
                                  ? "bg-[#6d28d9] text-white rounded-br-sm"
                                  : "bg-[#1e1e2e] text-gray-100 rounded-bl-sm border border-[#2a2a3d]"
                              }`}
                            >
                              {msg.content?.includes("TIMESLOTS::")
                                ? "[Slot picker shown to user]"
                                : msg.content}
                            </div>
                            {msg.type === "quick_reply" && (
                              <span className="text-xs bg-[#2a2a3d] text-purple-400 px-2 py-0.5 rounded-full border border-purple-800">
                                Quick reply
                              </span>
                            )}
                            {msg.timestamp && (
                              <span className="text-[10px] text-gray-600 px-1">
                                {new Date(msg.timestamp).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                            )}
                          </div>
                        );
                      })
                    )}
                    <div ref={chatEndRef} />
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-[50vh] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] text-sm text-zinc-400">
                Select a conversation to view
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
