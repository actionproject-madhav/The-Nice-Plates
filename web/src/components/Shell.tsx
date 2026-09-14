/** Page chrome: masthead, nav, colophon. */

import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Practice log", end: true },
  { to: "/library", label: "Library" },
  { to: "/coach", label: "Coach" },
];

export function Shell() {

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
          </nav>
        </div>
      </header>

      <main>
        <Outlet />
      </main>

      <footer>
        <div className="colophon">
          <span>CS Capstone</span>
        </div>
      </footer>
    </div>
  );
}
