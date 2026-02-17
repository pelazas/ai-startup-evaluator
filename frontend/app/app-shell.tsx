"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/contexts/auth-context";

const HIDDEN_NAV_PATHS = new Set(["/login", "/signup"]);

function initialsFromEmail(email: string | undefined): string {
  if (!email) {
    return "U";
  }
  return email.slice(0, 1).toUpperCase();
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const shouldShowNav = isAuthenticated && !HIDDEN_NAV_PATHS.has(pathname);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!menuRef.current) {
        return;
      }
      if (!menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <>
      {shouldShowNav ? (
        <header className="top-nav">
          <div className="top-nav-inner">
            <Link href="/evaluate" className="top-nav-brand">
              AI Startup Audit
            </Link>
            <div className="profile-menu-wrap" ref={menuRef}>
              <button
                type="button"
                className="profile-icon-button"
                onClick={() => setMenuOpen((prev) => !prev)}
                aria-label="Open profile menu"
                aria-expanded={menuOpen}
              >
                {initialsFromEmail(user?.email)}
              </button>
              {menuOpen ? (
                <div className="profile-menu">
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      router.push("/profile/edit");
                    }}
                  >
                    Edit profile
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      logout();
                    }}
                  >
                    Log out
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>
      ) : null}
      {children}
    </>
  );
}
