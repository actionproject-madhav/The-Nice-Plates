import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { useAuth } from "./lib/auth";
import { Dashboard } from "./pages/Dashboard";
import { Library } from "./pages/Library";
import { PiecePage } from "./pages/PiecePage";
import { Practice } from "./pages/Practice";
import { Coach } from "./pages/Coach";

export function App() {
  const { loading, waiting, error } = useAuth();

  if (loading) {
    // Under three seconds, say nothing — a spinner for a 300ms request is
    // noise. Past that it is a sleeping free instance, so say so.
    return (
      <div className="shell">
        <main>
          {waiting >= 3 && (
            <div className="reveal">
              <p className="eyebrow">Waking the server</p>
              <p className="lede small">
                It sleeps when nobody has practised for a while. Up to a minute.
              </p>
            </div>
          )}
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="shell">
        <main>
          <p className="notice" data-tone="bad">
            Can’t reach the server right now.
          </p>
        </main>
      </div>
    );
  }

  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Dashboard />} />
        <Route path="library" element={<Library />} />
        <Route path="piece/:pieceId" element={<PiecePage />} />
        <Route path="practice/:pieceId" element={<Practice />} />
        <Route path="coach" element={<Coach />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
