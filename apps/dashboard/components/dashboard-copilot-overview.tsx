"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CalendarClock,
  ChevronDown,
  ChevronRight,
  MessageCircle,
  PhoneCall,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";

type DashboardRecommendation = {
  id: string;
  type: string;
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  href: string | null;
};

type DashboardOverview = {
  generated_at: string;
  timezone: string;
  clinic_id: string;
  unread_messages: number;
  unread_threads: number;
  pending_confirmations: number;
  patients_to_recall: number;
  late_active: number;
  released_slots: number;
  alerts: number;
  recommendations: DashboardRecommendation[];
};

function metricDetail(count: number, singular: string, plural: string) {
  return count === 1 ? singular : plural;
}

export function DashboardCopilotOverview() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recommendationsOpen, setRecommendationsOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadOverview() {
      try {
        const response = await fetch(
          "/api/copilot/dashboard-overview",
          {
            cache: "no-store",
            signal: controller.signal,
          },
        );

        const body = (await response.json()) as DashboardOverview | { detail?: string };

        if (!response.ok) {
          throw new Error(
            "detail" in body && body.detail
              ? body.detail
              : `Dashboard Copilote indisponible (${response.status}).`,
          );
        }

        setOverview(body as DashboardOverview);
        setError(null);
      } catch (caughtError) {
        if (
          caughtError instanceof DOMException &&
          caughtError.name === "AbortError"
        ) {
          return;
        }

        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de charger les priorités du Copilote.",
        );
      }
    }

    void loadOverview();

    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <section className="dashboard-copilot-overview dashboard-copilot-error">
        <AlertTriangle size={18} />
        <span>{error}</span>
      </section>
    );
  }

  if (!overview) {
    return (
      <section className="dashboard-copilot-overview dashboard-copilot-loading">
        <Sparkles size={18} />
        <span>Le Copilote prépare les priorités du jour…</span>
      </section>
    );
  }

  const metrics = [
    {
      label: "Conversations à traiter",
      value: overview.unread_threads,
      detail: `${overview.unread_messages} ${metricDetail(
        overview.unread_messages,
        "message non lu",
        "messages non lus",
      )}`,
      href: "/conversations",
      icon: MessageCircle,
    },
    {
      label: "À confirmer",
      value: overview.pending_confirmations,
      detail: metricDetail(
        overview.pending_confirmations,
        "rendez-vous en attente",
        "rendez-vous en attente",
      ),
      href: "/appointments",
      icon: CalendarClock,
    },
    {
      label: "Patients à rappeler",
      value: overview.patients_to_recall,
      detail: "Suivis préventifs détectés",
      href: "/copilot",
      icon: PhoneCall,
    },
    {
      label: "Alertes",
      value: overview.alerts,
      detail: `${overview.released_slots} créneau(x) libéré(s) · ${overview.late_active} retard(s)`,
      href: "/appointments",
      icon: AlertTriangle,
    },
  ];

  return (
    <section className="dashboard-copilot-overview">
      <header className="dashboard-copilot-header">
        <div>
          <span className="dashboard-copilot-kicker">
            <Sparkles size={15} />
            Copilote DentalFlow
          </span>
          <h2>Priorités du jour</h2>
          <p>Ce qui mérite votre attention maintenant.</p>
        </div>

        <Link href="/copilot" className="dashboard-copilot-open-link">
          Ouvrir le Copilote
          <ChevronRight size={16} />
        </Link>
      </header>

      <div className="dashboard-copilot-metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <Link
              className="dashboard-copilot-metric"
              href={metric.href}
              key={metric.label}
            >
              <span className="dashboard-copilot-metric-icon">
                <Icon size={18} />
              </span>
              <div>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <small>{metric.detail}</small>
              </div>
            </Link>
          );
        })}
      </div>

      <div className="dashboard-copilot-recommendations">
        <button
          className={`dashboard-copilot-recommendation-toggle${
            recommendationsOpen ? " open" : ""
          }`}
          onClick={() =>
            setRecommendationsOpen((current) => !current)
          }
          type="button"
        >
          <span>
            <Sparkles size={16} />
            Recommandations
          </span>

          <span className="dashboard-copilot-recommendation-toggle-meta">
            {overview.recommendations.length}
            <ChevronDown size={17} />
          </span>
        </button>

        {recommendationsOpen && overview.recommendations.length > 0 ? (
          <div className="dashboard-copilot-recommendation-list">
            {overview.recommendations.map((recommendation, index) => {
              const content = (
                <>
                  <span className={`dashboard-copilot-rank ${recommendation.priority}`}>
                    {index + 1}
                  </span>
                  <div>
                    <strong>{recommendation.title}</strong>
                    <p>{recommendation.description}</p>
                  </div>
                  {recommendation.href ? <ChevronRight size={17} /> : null}
                </>
              );

              return recommendation.href ? (
                <Link
                  className="dashboard-copilot-recommendation"
                  href={recommendation.href}
                  key={recommendation.id}
                >
                  {content}
                </Link>
              ) : (
                <article
                  className="dashboard-copilot-recommendation"
                  key={recommendation.id}
                >
                  {content}
                </article>
              );
            })}
          </div>
        ) : recommendationsOpen ? (
          <p className="dashboard-copilot-empty">
            Aucune action prioritaire détectée pour le moment.
          </p>
        ) : null}
      </div>
    </section>
  );
}
