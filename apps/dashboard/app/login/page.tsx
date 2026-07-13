"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("owner@dentalflow.ai");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      const body = await response.json();

      if (!response.ok) {
        setError(
          typeof body.detail === "string"
            ? body.detail
            : "Connexion impossible.",
        );
        return;
      }

      router.replace("/");
      router.refresh();
    } catch {
      setError("Le serveur est momentanément indisponible.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand">
          <span>DF</span>
          <div>
            <strong>DentalFlow AI</strong>
            <p>Espace clinique sécurisé</p>
          </div>
        </div>

        <div className="login-heading">
          <p className="eyebrow">Bienvenue</p>
          <h1>Connectez-vous</h1>
          <p>Accédez à votre agenda et à vos dossiers patients.</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Adresse e-mail
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label>
            Mot de passe
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" disabled={loading}>
            {loading ? "Connexion…" : "Se connecter"}
          </button>
        </form>
      </section>
    </main>
  );
}
