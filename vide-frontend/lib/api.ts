import { adminGet, adminPost } from "@/lib/apiClient";

export interface LeadFilters {
  stage?: string;
  min_score?: number;
  converted?: boolean;
  objection_type?: string;
}

export interface Lead {
  id: string;
  name: string;
  email: string;
  business_name: string;
  video_type: string;
  budget: number;
  lead_score: number;
  recommended_package: string;
  order_confirmed: boolean;
  created_at: string;
}

export interface Message {
  role: string;
  content: string;
  timestamp: string;
}

export interface Conversation {
  conversation_id: string;
  stage: string;
  lead_score: number;
  messages: Message[];
  created_at: string;
}

export interface LoginResponse {
  token: string;
  email: string;
  message: string;
}

function withQuery(path: string, filters?: LeadFilters): string {
  if (!filters) {
    return path;
  }

  const searchParams = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `${path}?${query}` : path;
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return adminPost<LoginResponse>("/api/v1/admin/login", { email, password });
}

export function getLeads(filters?: LeadFilters): Promise<Lead[]> {
  return adminGet<Lead[]>(withQuery("/api/v1/admin/leads", filters));
}

export function getChats(conversationId: string): Promise<Message[]> {
  return adminGet<Message[]>(`/api/v1/admin/chats/${conversationId}`);
}

export function getAllConversations(): Promise<Conversation[]> {
  return adminGet<Conversation[]>("/api/v1/admin/conversations");
}

export function sendFollowupEmail(
  leadId: string,
  emailType: string
): Promise<unknown> {
  return adminPost("/api/v1/admin/email/followup", {
    lead_id: leadId,
    email_type: emailType,
  });
}
