// Shapes returned by the FastAPI backend (see ARCHITECTURE.md / backend routers).

export type Role = "owner" | "editor" | "viewer";
export type ShareRole = Exclude<Role, "owner">;

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface DocSummary {
  id: number;
  title: string;
  updated_at: string;
}

export interface SharedDocSummary extends DocSummary {
  role: ShareRole;
  owner_name: string;
}

export interface DocLists {
  owned: DocSummary[];
  shared: SharedDocSummary[];
}

export interface Share {
  user_id: number;
  name: string;
  email: string;
  role: ShareRole;
}

export interface Doc {
  id: number;
  title: string;
  content: string; // sanitized HTML
  version: number;
  updated_at: string;
  updated_by: string | null;
  owner: { id: number; name: string };
  role: Role;
  shares: Share[];
  active_users: string[];
}

export interface Created {
  id: number;
}

export interface Saved {
  version: number;
}

export interface SharesResponse {
  shares: Share[];
}
