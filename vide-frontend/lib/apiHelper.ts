import { adminDelete, adminGet, adminPut } from "@/lib/apiClient";

const LEAD_OVERRIDES_KEY = "admin_lead_overrides";

type ConversationIdentity = {
  id?: string | null;
  conversation_id?: string | null;
  name?: string | null;
  email?: string | null;
  business_name?: string | null;
  recommended_package?: string | null;
  budget?: number | null;
  lead_score?: number | null;
  order_confirmed?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
  messages?: unknown[];
  message_count?: number | null;
  stage?: string | null;
  sales_mode?: string | null;
};

export type LeadOverrideFields = {
  name?: string;
  email?: string;
  phone?: string;
};

type LeadOverrideRecord = Record<string, LeadOverrideFields>;

export { adminDelete, adminGet, adminPut };

const readLeadOverrides = (): LeadOverrideRecord => {
  if (typeof window === "undefined") {
    return {};
  }

  const raw = sessionStorage.getItem(LEAD_OVERRIDES_KEY);

  if (!raw) {
    return {};
  }

  try {
    return JSON.parse(raw) as LeadOverrideRecord;
  } catch {
    return {};
  }
};

const writeLeadOverrides = (overrides: LeadOverrideRecord) => {
  if (typeof window === "undefined") {
    return;
  }

  sessionStorage.setItem(LEAD_OVERRIDES_KEY, JSON.stringify(overrides));
};

export const saveLeadOverride = (
  conversationId: string,
  data: LeadOverrideFields
) => {
  const overrides = readLeadOverrides();
  overrides[conversationId] = {
    ...overrides[conversationId],
    ...data,
  };
  writeLeadOverrides(overrides);
};

export const removeLeadOverride = (conversationId: string) => {
  const overrides = readLeadOverrides();
  delete overrides[conversationId];
  writeLeadOverrides(overrides);
};

export const applyLeadOverrides = <
  T extends { conversation_id?: string; id?: string }
>(
  items: T[]
): T[] => {
  const overrides = readLeadOverrides();

  return items.map((item) => {
    const key = item.conversation_id || item.id;

    if (!key || !overrides[key]) {
      return item;
    }

    return {
      ...item,
      ...overrides[key],
    };
  });
};

export const applyLeadOverride = <
  T extends { conversation_id?: string; id?: string }
>(
  item: T
): T => {
  const [merged] = applyLeadOverrides([item]);
  return merged;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const getNestedValue = (record: Record<string, unknown>, path: string[]) => {
  let current: unknown = record;

  for (const key of path) {
    if (!isRecord(current) || !(key in current)) {
      return undefined;
    }

    current = current[key];
  }

  return current;
};

const asString = (value: unknown) => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return undefined;
};

const asNumber = (value: unknown) => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  return undefined;
};

const asBoolean = (value: unknown) => {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    if (value === "true") {
      return true;
    }

    if (value === "false") {
      return false;
    }
  }

  return undefined;
};

const firstDefined = (...values: unknown[]) =>
  values.find((value) => value !== undefined && value !== null);

const extractMessagesFromUnknown = (payload: unknown): unknown[] => {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (!isRecord(payload)) {
    return [];
  }

  const candidates = [
    payload.messages,
    payload.chat,
    payload.history,
    payload.conversation,
    payload.conversation_data,
    payload.transcript,
    payload.entries,
    payload.items,
    payload.results,
    payload.data,
  ];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate;
    }

    if (isRecord(candidate)) {
      const nested = extractMessagesFromUnknown(candidate);

      if (nested.length > 0) {
        return nested;
      }
    }
  }

  return [];
};

const normalizeConversationRecord = <T extends Record<string, unknown>>(
  item: T
): T => {
  const conversationId = asString(
    firstDefined(
      item.conversation_id,
      item.id,
      item.conversationId,
      getNestedValue(item, ["conversation", "id"]),
      getNestedValue(item, ["lead", "conversation_id"])
    )
  );
  const name = asString(
    firstDefined(
      item.name,
      item.user_name,
      item.lead_name,
      item.customer_name,
      item.full_name,
      getNestedValue(item, ["lead", "name"]),
      getNestedValue(item, ["customer", "name"]),
      getNestedValue(item, ["user", "name"])
    )
  );
  const email = asString(
    firstDefined(
      item.email,
      item.user_email,
      item.lead_email,
      item.customer_email,
      getNestedValue(item, ["lead", "email"]),
      getNestedValue(item, ["customer", "email"]),
      getNestedValue(item, ["user", "email"])
    )
  );
  const businessName = asString(
    firstDefined(
      item.business_name,
      item.company_name,
      item.brand_name,
      getNestedValue(item, ["lead", "business_name"]),
      getNestedValue(item, ["customer", "business_name"])
    )
  );
  const recommendedPackage = asString(
    firstDefined(
      item.recommended_package,
      item.package_name,
      item.package,
      getNestedValue(item, ["lead", "recommended_package"])
    )
  );
  const leadScore = asNumber(
    firstDefined(
      item.lead_score,
      item.score,
      getNestedValue(item, ["lead", "lead_score"])
    )
  );
  const orderConfirmed = asBoolean(
    firstDefined(
      item.order_confirmed,
      item.converted,
      getNestedValue(item, ["lead", "order_confirmed"])
    )
  );
  const stage = asString(
    firstDefined(
      item.stage,
      item.current_stage,
      getNestedValue(item, ["lead", "stage"])
    )
  );
  const salesMode = asString(
    firstDefined(
      item.sales_mode,
      item.mode,
      getNestedValue(item, ["lead", "sales_mode"])
    )
  );
  const createdAt = asString(
    firstDefined(
      item.created_at,
      item.createdAt,
      item.timestamp,
      getNestedValue(item, ["lead", "created_at"])
    )
  );
  const updatedAt = asString(
    firstDefined(
      item.updated_at,
      item.updatedAt,
      getNestedValue(item, ["lead", "updated_at"])
    )
  );
  const budget = asNumber(
    firstDefined(item.budget, getNestedValue(item, ["lead", "budget"]))
  );
  const messageCount = asNumber(
    firstDefined(
      item.message_count,
      item.total_messages,
      item.totalMessages,
      extractMessagesFromUnknown(item).length
    )
  );
  const messages = extractMessagesFromUnknown(item);

  return {
    ...item,
    ...(conversationId ? { conversation_id: conversationId, id: conversationId } : {}),
    ...(name ? { name } : {}),
    ...(email ? { email } : {}),
    ...(businessName ? { business_name: businessName } : {}),
    ...(recommendedPackage ? { recommended_package: recommendedPackage } : {}),
    ...(leadScore !== undefined ? { lead_score: leadScore } : {}),
    ...(orderConfirmed !== undefined ? { order_confirmed: orderConfirmed } : {}),
    ...(stage ? { stage } : {}),
    ...(salesMode ? { sales_mode: salesMode } : {}),
    ...(createdAt ? { created_at: createdAt } : {}),
    ...(updatedAt ? { updated_at: updatedAt } : {}),
    ...(budget !== undefined ? { budget } : {}),
    ...(messageCount !== undefined ? { message_count: messageCount } : {}),
    ...(messages.length > 0 ? { messages } : {}),
  } as T;
};

export const extractAdminCollection = <T>(payload: unknown): T[] => {
  if (Array.isArray(payload)) {
    return payload.map((item) =>
      isRecord(item) ? (normalizeConversationRecord(item) as T) : (item as T)
    );
  }

  if (!isRecord(payload)) {
    return [];
  }

  const directKeys = ["data", "conversations", "results", "items", "leads"];

  for (const key of directKeys) {
    const value = payload[key];
    if (Array.isArray(value)) {
      return value.map((item) =>
        isRecord(item) ? (normalizeConversationRecord(item) as T) : (item as T)
      );
    }
  }

  if (isRecord(payload.data)) {
    for (const key of directKeys) {
      const value = payload.data[key];
      if (Array.isArray(value)) {
        return value.map((item) =>
          isRecord(item) ? (normalizeConversationRecord(item) as T) : (item as T)
        );
      }
    }
  }

  return [];
};

const normalizeIdentityValue = (value: string | null | undefined) =>
  value?.trim().toLowerCase() || "";

const getConversationIdentityKey = (item: ConversationIdentity) => {
  const email = normalizeIdentityValue(item.email);

  if (email) {
    return `email:${email}`;
  }

  const name = normalizeIdentityValue(item.name);
  const business = normalizeIdentityValue(item.business_name);

  if (name && business) {
    return `person:${name}:${business}`;
  }

  if (name) {
    return `name:${name}`;
  }

  return item.conversation_id || item.id || "";
};

const getRecordTimestamp = (item: ConversationIdentity) => {
  const raw = item.updated_at || item.created_at;
  const timestamp = raw ? new Date(raw).getTime() : Number.NaN;
  return Number.isNaN(timestamp) ? -1 : timestamp;
};

const getRecordCompleteness = (item: ConversationIdentity) => {
  const fields = [
    item.name,
    item.email,
    item.business_name,
    item.recommended_package,
    item.created_at,
    item.updated_at,
  ];

  return fields.filter((value) => {
    if (typeof value === "string") {
      return value.trim().length > 0;
    }

    return value !== null && value !== undefined;
  }).length;
};

const pickPreferredRecord = <T extends ConversationIdentity>(current: T, next: T) => {
  const currentTimestamp = getRecordTimestamp(current);
  const nextTimestamp = getRecordTimestamp(next);

  if (nextTimestamp !== currentTimestamp) {
    return nextTimestamp > currentTimestamp ? next : current;
  }

  return getRecordCompleteness(next) > getRecordCompleteness(current)
    ? next
    : current;
};

const mergeConversationRecords = <T extends ConversationIdentity>(
  current: T,
  next: T
) => {
  const preferred = pickPreferredRecord(current, next);
  const fallback = preferred === current ? next : current;
  const preferredMessages = Array.isArray(preferred.messages)
    ? preferred.messages
    : [];
  const fallbackMessages = Array.isArray(fallback.messages)
    ? fallback.messages
    : [];

  return {
    ...fallback,
    ...preferred,
    conversation_id: preferred.conversation_id || fallback.conversation_id,
    id: preferred.id || fallback.id,
    message_count:
      Math.max(
        preferred.message_count ?? preferredMessages.length,
        fallback.message_count ?? fallbackMessages.length
      ) || 0,
    messages:
      preferredMessages.length >= fallbackMessages.length
        ? preferredMessages
        : fallbackMessages,
  };
};

export const dedupeLeadRecords = <T extends ConversationIdentity>(items: T[]): T[] => {
  const deduped = new Map<string, T>();

  for (const item of items) {
    const key =
      getConversationIdentityKey(item) ||
      `unknown:${item.conversation_id || item.id || deduped.size}`;

    const existing = deduped.get(key);

    if (!existing) {
      deduped.set(key, item);
      continue;
    }

    deduped.set(key, mergeConversationRecords(existing, item) as T);
  }

  return Array.from(deduped.values()).sort((a, b) => {
    return getRecordTimestamp(b) - getRecordTimestamp(a);
  });
};

export const loadAdminConversations = async <
  T extends { conversation_id?: string; id?: string }
>(
  path = "/api/v1/admin/conversations"
): Promise<T[]> => {
  const payload = await adminGet(path);
  const items = extractAdminCollection<T>(payload);
  return dedupeLeadRecords(applyLeadOverrides(items));
};

export const extractChatMessages = <T>(payload: unknown): T[] => {
  const rawMessages = extractMessagesFromUnknown(payload);

  return rawMessages
    .map((item) => {
      if (!isRecord(item)) {
        const content = asString(item);

        return content
          ? ({
              role: "assistant",
              content,
            } as T)
          : null;
      }

      const role =
        asString(
          firstDefined(
            item.role,
            item.sender,
            item.type,
            item.author,
            getNestedValue(item, ["metadata", "role"])
          )
        ) || "assistant";
      const content =
        asString(
          firstDefined(
            item.content,
            item.message,
            item.text,
            item.body,
            item.response,
            getNestedValue(item, ["payload", "content"]),
            getNestedValue(item, ["payload", "text"])
          )
        ) || "";
      const timestamp = asString(
        firstDefined(
          item.timestamp,
          item.created_at,
          item.createdAt,
          item.time,
          getNestedValue(item, ["metadata", "timestamp"])
        )
      );

      if (!content) {
        return null;
      }

      return {
        ...item,
        role,
        content,
        ...(timestamp ? { timestamp } : {}),
      } as T;
    })
    .filter((item): item is T => item !== null);
};
