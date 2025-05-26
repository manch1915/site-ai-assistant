export type Role = "visitor" | "bot" | "manager" | "system";
export type Status = "bot" | "waiting" | "human" | "closed";
export type Action = "handoff" | "lead";

export interface Source {
  title: string;
  url: string | null;
  snippet?: string;
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

export interface WidgetConfig {
  site_name: string;
  settings: WidgetSettings;
  handoff_available: boolean;
}

export interface ServerMessage {
  id: number;
  role: Role;
  content: string;
  author: string | null;
  sources: Source[];
  created_at: string;
}

export interface ChatMessage {
  key: string;
  role: Role;
  content: string;
  author?: string | null;
  sources?: Source[];
  actions?: Action[];
  streaming?: boolean;
  rateable?: boolean;
}

export interface MountOptions {
  apiBase: string;
  siteKey: string;
  root: ShadowRoot | HTMLElement;
  config: WidgetConfig;
  inline?: boolean;
  startOpen?: boolean;
  onClose?: () => void;
}
