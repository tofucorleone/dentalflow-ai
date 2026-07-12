"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function logout() {
    setLoading(true);

    try {
      await fetch("/api/auth/logout", {
        method: "POST",
      });

      router.replace("/login");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      className="logout-button"
      disabled={loading}
      onClick={logout}
      type="button"
    >
      {loading ? "Déconnexion…" : "Se déconnecter"}
    </button>
  );
}
