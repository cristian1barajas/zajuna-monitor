"use client";

/**
 * Badge del usuario autenticado (sesión CMM) con botón de cerrar sesión.
 * Vive en el pie del sidebar. Se autoabastece vía GET /auth/me.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { clearReadCache } from "@/lib/api";
import {
  getMe,
  getAccessToken,
  logoutUser,
  type AuthUser,
} from "@/lib/cmm-auth";

export function UserBadge() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    getMe(token)
      .then(setUser)
      .catch(() => {});
  }, []);

  const handleLogout = async () => {
    await logoutUser();
    clearReadCache();
    router.replace("/login");
  };

  if (!user) return null;

  const initials = user.full_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");

  return (
    <div className="mx-3 mb-3 flex items-center gap-3 rounded-xl bg-active-pill px-3 py-2.5 text-white shadow-sm">
      <span
        aria-hidden="true"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sena-teal-deep text-xs font-bold tracking-wide text-white"
      >
        {initials}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-bold uppercase tracking-wide" title={user.email}>
          {user.full_name}
        </p>
        <p className="text-[11px] capitalize text-white/85">{user.role}</p>
      </div>
      <button
        onClick={handleLogout}
        title="Cerrar sesión"
        aria-label="Cerrar sesión"
        className="shrink-0 cursor-pointer rounded-full p-2 text-white transition-colors duration-150 ease-out hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
      >
        <LogOut aria-hidden="true" className="h-4 w-4" />
      </button>
    </div>
  );
}
