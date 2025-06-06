export type ConversationStatus = "bot" | "waiting" | "human" | "closed";
export type SourceKind = "sitemap" | "url" | "file" | "faq";
export type SourceStatus = "queued" | "indexing" | "ready" | "failed";
export type LeadStatus = "new" | "in_progress" | "done";
export type Role = "visitor" | "bot" | "manager" | "system";

export interface SiteBrief {
  id: string;
  name: string;
  public_key: string;
}

export interface Me {
  id: string;
  name: string;
  email: string;
  is_demo: boolean;
  workspace: string;
  sites: SiteBrief[];
}

export interface WidgetSettings {
  title: string;
  subtitle: string;
  greeting: string;
  accent: string;
  theme: "light" | "dark" | "auto";
  position: "right" | "left";
  radius: number;
  quick_questions: string[];
  language: "auto" | "en" | "ru";
  show_sources: boolean;
  collect_leads: boolean;
  handoff_enabled: boolean;
}

export interface Site {
  id: string;
  name: string;
  public_key: string;
  allowed_domains: string[];
  widget: WidgetSettings;
  instructions: string;
  confidence_threshold: number;
  monthly_token_budget: number;
  telegram_chat_title: string | null;
  created_at: string;
}

export interface Source {
  id: string;
  kind: SourceKind;
  title: string;
  url: string | null;
  status: SourceStatus;
  error: string | null;
  documents_count: number;
  chunks_count: number;
  indexed_at: string | null;
  created_at: string;
}

export interface FaqItem {
  id: string;
  question: string;
  answer: string;
  updated_at: string;
}

export interface Gap {
  id: string;
  question: string;
  times_asked: number;
  status: "open" | "answered" | "dismissed";
  last_asked_at: string;
}

export interface ConversationRow {
  id: string;
  status: ConversationStatus;
  language: string;
  page_url: string | null;
  created_at: string;
  last_message_at: string;
  preview: string;
  messages: number;
  unanswered: number;
  rating: number | null;
  has_lead: boolean;
}

export interface MessageSource {
  title: string;
  url: string | null;
  snippet?: string;
}

export interface Message {
  id: number;
  role: Role;
  content: string;
  author_name: string | null;
  sources: MessageSource[];
  confidence: number | null;
  answered: boolean | null;
  flagged: boolean;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  status: ConversationStatus;
  language: string;
  page_url: string | null;
  rating: number | null;
  manager_name: string | null;
  created_at: string;
  messages: Message[];
}

export interface Lead {
  id: string;
  name: string;
  contact: string;
  question: string;
  status: LeadStatus;
  conversation_id: string | null;
  created_at: string;
}

export interface Overview {
  days: number;
  conversations: number;
  resolved_confirmed: number;
  resolved_assumed: number;
  handoffs: number;
  leads: number;
  unanswered_messages: number;
  automation_rate: number;
  series: { day: string; conversations: number; handoffs: number }[];
  top_gaps: { id: string; question: string; times_asked: number }[];
  tokens_this_month: number;
  token_budget: number;
  llm_enabled: boolean;
}

export interface TelegramStatus {
  enabled: boolean;
  connected: boolean;
  chat_title: string | null;
  connect_link: string | null;
}
