/**
 * Auth context.
 *
 * Holds the signed-in user, restores the session on load, and renders the
 * Google button. Google's script is loaded in index.html; if it hasn't landed
 * yet we poll briefly rather than racing it.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, setToken, type User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  signInWithGoogle: (credential: string) => Promise<void>;
  signInAsDev: () => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sign-in is switched off for now: land straight in the app. The API issues
  // a session without a password while Google is unconfigured. Restore the
  // gate by deleting the devLogin fallback here and re-adding the <SignIn/>
  // branch in App.tsx.
  useEffect(() => {
    let cancelled = false;

    async function enter() {
      try {
        if (getToken()) {
          const existing = await api.me();
          if (!cancelled) setUser(existing);
          return;
        }
      } catch {
        setToken(null); // expired or revoked — fall through and get a new one
      }
      try {
        const fresh = await api.devLogin();
        if (cancelled) return;
        setToken(fresh.access_token);
        setUser(fresh.user);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Couldn't reach the server.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void enter().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const adopt = useCallback((token: string, u: User) => {
    setToken(token);
    setUser(u);
    setError(null);
  }, []);

  const signInWithGoogle = useCallback(
    async (credential: string) => {
      setError(null);
      try {
        const result = await api.googleLogin(credential);
        adopt(result.access_token, result.user);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Sign-in failed.");
      }
    },
    [adopt],
  );

  const signInAsDev = useCallback(async () => {
    setError(null);
    try {
      const result = await api.devLogin();
      adopt(result.access_token, result.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed.");
    }
  }, [adopt]);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, error, signInWithGoogle, signInAsDev, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside an AuthProvider");
  return ctx;
}

// ── Google Identity Services ────────────────────────────────────────────────

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (r: { credential: string }) => void;
          }) => void;
          renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

export function GoogleButton() {
  const { signInWithGoogle } = useAuth();
  const slot = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!CLIENT_ID || !slot.current) return;

    let cancelled = false;
    // The GSI script is async; wait for it rather than assuming it has landed.
    const tick = window.setInterval(() => {
      if (cancelled || !window.google || !slot.current) return;
      window.clearInterval(tick);
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: (r) => void signInWithGoogle(r.credential),
      });
      window.google.accounts.id.renderButton(slot.current, {
        type: "standard",
        theme: "outline",
        size: "large",
        shape: "pill",
        text: "continue_with",
        logo_alignment: "left",
      });
      setReady(true);
    }, 120);

    const giveUp = window.setTimeout(() => window.clearInterval(tick), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(tick);
      window.clearTimeout(giveUp);
    };
  }, [signInWithGoogle]);

  if (!CLIENT_ID) {
    return (
      <p className="notice">
        Google sign-in isn’t configured. Set <span className="mono">VITE_GOOGLE_CLIENT_ID</span> to
        switch it on.
      </p>
    );
  }

  return (
    <div>
      <div ref={slot} />
      {!ready && <p className="small muted">Loading Google sign-in…</p>}
    </div>
  );
}
