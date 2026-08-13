"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

type LoginFormProps = {
  displayName: string;
  softwareName: string;
  logoUrl: string | null;
};

export function LoginForm({
  displayName,
  softwareName,
  logoUrl,
}: LoginFormProps) {
  const router = useRouter();

  const [email, setEmail] = useState("owner@dentalflow.ai");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const softwareInitial = (
    softwareName.trim().charAt(0) || "D"
  ).toUpperCase();

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
        }),
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
      setError(
        "Le serveur est momentanément indisponible.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand">
          <span>
            {logoUrl ? (
              <img
                src="/api/clinic-branding/logo"
                alt={`Logo ${displayName}`}
              />
            ) : (
              softwareInitial
            )}
          </span>

          <div>
            <strong>{softwareName}</strong>
            <p>{displayName}</p>
          </div>
        </div>

        <div className="login-heading">
          <p className="eyebrow">Bienvenue</p>
          <h1>Connectez-vous</h1>
          <p>
            Accédez à votre agenda et à vos dossiers patients.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="login-form"
        >
          <label>
            Adresse e-mail
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              required
            />
          </label>

          <label>
            Mot de passe
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              required
            />
          </label>

          {error ? (
            <div className="login-error">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Connexion…"
              : "Se connecter"}
          </button>
        </form>
      </section>
    </main>
  );
}
