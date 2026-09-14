/** Page chrome: masthead, nav, colophon. */

import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/", label: "Practice log", end: true },
  { to: "/library", label: "Library" },
  { to: "/coach", label: "Coach" },
];

export function Shell() {
  const { user, signOut } = useAuth();

  return (
    <div className="shell">
      <header className="masthead">
        <div className="masthead-inner">
          <NavLink to="/" className="wordmark">
            The Nice Plates
          </NavLink>
          <nav>
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className="navlink">
                {item.label}
              </NavLink>
            ))}
            {user && (
              <button type="button" className="navlink" onClick={signOut}>
                Sign out
              </button>
            )}
          </nav>
        </div>
      </header>

      <main>
        <Outlet />
      </main>

      <footer>
        <div className="colophon">
          <span>CS Capstone</span>
          <span>{user?.name ?? "Not signed in"}</span>
        </div>
      </footer>
    </div>
  );
}
