/**
 * API client.
 *
 * One fetch wrapper so auth headers, base URL and error shape are decided in
 * exactly one place. In dev the base URL is empty and Vite proxies /v1 to the
 * local API; in production it points at Render.
 */

const BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";
const TOKEN_KEY = "np.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // private windows and blocked site data
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* signed-in state simply won't survive a reload */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${BASE}${path}`, { ...init, headers });

  if (response.status === 401) {
    setToken(null);
    throw new ApiError(401, "Your session ended. Sign in again.");
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  health: () => request<ReadyCheck>("/health/ready"),

  googleLogin: (credential: string) =>
    request<AuthResponse>("/v1/auth/google", { method: "POST", body: json({ credential }) }),
  devLogin: () => request<AuthResponse>("/v1/auth/dev-login", { method: "POST" }),
  me: () => request<User>("/v1/auth/me"),

  listPieces: () => request<Piece[]>("/v1/pieces"),
  createPiece: (body: NewPiece) =>
    request<Piece>("/v1/pieces", { method: "POST", body: json(body) }),
  getPiece: (id: string) => request<PieceDetail>(`/v1/pieces/${id}`),
  deletePiece: (id: string) => request<void>(`/v1/pieces/${id}`, { method: "DELETE" }),
  chunkPiece: (id: string, totalBars: number, barsPerSection: number) =>
    request<Section[]>(`/v1/pieces/${id}/chunk`, {
      method: "POST",
      body: json({ total_bars: totalBars, bars_per_section: barsPerSection, replace_existing: true }),
    }),

  startSession: (body: { piece_id?: string; section_id?: string; tempo_bpm?: number }) =>
    request<Session>("/v1/sessions", { method: "POST", body: json(body) }),
  endSession: (id: string, durationSeconds: number, notes?: string) =>
    request<Session>(`/v1/sessions/${id}/end`, {
      method: "POST",
      body: json({ duration_seconds: durationSeconds, notes }),
    }),
  listSessions: () => request<Session[]>("/v1/sessions"),

  uploadUrl: (body: UploadRequest) =>
    request<UploadTicket>("/v1/recordings/upload-url", { method: "POST", body: json(body) }),
  completeUpload: (id: string, sizeBytes: number, durationSeconds?: number) =>
    request<{ job_id: string }>(`/v1/recordings/${id}/complete`, {
      method: "POST",
      body: json({ size_bytes: sizeBytes, duration_seconds: durationSeconds }),
    }),
  recording: (id: string) => request<RecordingStatus>(`/v1/recordings/${id}`),

  progress: () => request<Progress>("/v1/progress/summary"),

  askCoach: (message: string, threadId?: string, pieceId?: string) =>
    request<CoachReply>("/v1/coach/ask", {
      method: "POST",
      body: json({ message, thread_id: threadId, piece_id: pieceId }),
    }),
};

/** PUT the recorded bytes straight to object storage, bypassing the API. */
export async function putToStorage(ticket: UploadTicket, blob: Blob): Promise<void> {
  const url = ticket.upload_url.startsWith("http")
    ? ticket.upload_url
    : `${BASE}${ticket.upload_url}`;
  const response = await fetch(url, {
    method: ticket.method,
    headers: ticket.headers,
    body: blob,
  });
  if (!response.ok) {
    throw new ApiError(response.status, "That upload didn't go through. Try the take again.");
  }
}

// ── Types (mirror the FastAPI schemas) ──────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  picture: string | null;
  role: string;
  instrument: string | null;
}

export interface AuthResponse {
  access_token: string;
  expires_in: number;
  user: User;
}

export interface ReadyCheck {
  status: "ok" | "degraded" | "down";
  checks: Record<string, { ok: boolean; required: boolean; note?: string; backend?: string }>;
  queue_depth: number;
}

export interface NewPiece {
  title: string;
  composer?: string;
  instrument?: string;
  tempo_bpm?: number;
}

export interface Piece extends NewPiece {
  id: string;
  created_at: string;
  updated_at: string;
  tags: string[];
}

export interface Section {
  id: string;
  piece_id: string;
  index: number;
  label: string;
  start_bar: number;
  end_bar: number;
  difficulty: number;
}

export interface PieceDetail extends Piece {
  sections: Section[];
}

export interface Session {
  id: string;
  piece_id: string | null;
  section_id: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  notes: string | null;
}

export interface UploadRequest {
  filename: string;
  content_type: string;
  session_id?: string;
  piece_id?: string;
  section_id?: string;
}

export interface UploadTicket {
  recording_id: string;
  key: string;
  upload_url: string;
  method: string;
  headers: Record<string, string>;
  expires_in: number;
  backend: string;
}

export interface Feedback {
  pitch_accuracy: number;
  timing_accuracy: number;
  tempo_bpm_detected: number | null;
  tempo_stability: number | null;
  notes_expected: number;
  notes_played: number;
  problem_bars: number[];
  summary: string;
  engine: string;
}

export interface RecordingStatus {
  recording_id: string;
  status: "pending" | "uploaded" | "analyzing" | "analyzed" | "failed";
  job_status: string | null;
  feedback: Feedback | null;
  playback_url: string | null;
  error: string | null;
}

export interface DaySummary {
  date: string;
  minutes: number;
  sessions: number;
}

export interface Progress {
  total_minutes: number;
  total_sessions: number;
  current_streak_days: number;
  longest_streak_days: number;
  pieces_practiced: number;
  recent_days: DaySummary[];
  pitch_accuracy_trend: number[];
}

export interface CoachReply {
  thread_id: string;
  reply: string;
  tools_used: string[];
  model: string;
}
