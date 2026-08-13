from datetime import datetime, timedelta
from uuid import UUID


async def list_overdue_recall_patients(
    *,
    cur,
    clinic_id: UUID,
    now: datetime,
    minimum_months: int = 12,
    limit: int = 20,
) -> list[dict]:
    """
    Retourne des patients actifs à recontacter.

    Critères :
    - au moins un rendez-vous terminé ;
    - dernier rendez-vous terminé antérieur au seuil ;
    - aucun rendez-vous futur pending ou confirmed ;
    - lecture seule.
    """

    safe_months = min(max(minimum_months, 1), 60)
    safe_limit = min(max(limit, 1), 100)
    cutoff = now - timedelta(days=safe_months * 30)

    await cur.execute(
        """
        SELECT
            p.id AS patient_id,
            p.full_name AS patient_name,
            p.phone,
            p.email,
            MAX(a.start_at) FILTER (
                WHERE a.status = 'completed'
            ) AS last_completed_at
        FROM patients p
        JOIN appointments a
          ON a.clinic_id = p.clinic_id
         AND a.patient_id = p.id
        WHERE p.clinic_id = %s
          AND p.active = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM appointments future_appointment
              WHERE future_appointment.clinic_id = p.clinic_id
                AND future_appointment.patient_id = p.id
                AND future_appointment.status IN (
                    'pending',
                    'confirmed'
                )
                AND future_appointment.start_at >= %s
          )
        GROUP BY
            p.id,
            p.full_name,
            p.phone,
            p.email
        HAVING MAX(a.start_at) FILTER (
            WHERE a.status = 'completed'
        ) IS NOT NULL
           AND MAX(a.start_at) FILTER (
               WHERE a.status = 'completed'
           ) < %s
        ORDER BY
            last_completed_at ASC,
            p.full_name NULLS LAST
        LIMIT %s
        """,
        (
            clinic_id,
            now,
            cutoff,
            safe_limit,
        ),
    )

    return await cur.fetchall()


def enrich_overdue_recall_patients(
    *,
    patients: list[dict],
    now: datetime,
) -> list[dict]:
    enriched = []

    for patient in patients:
        last = patient["last_completed_at"]

        months = max(
            0,
            int((now - last).days / 30),
        )

        score = 30
        reasons = []

        if months >= 24:
            score += 40
            reasons.append(
                "Dernière visite il y a plus de 24 mois"
            )
        elif months >= 18:
            score += 25
            reasons.append(
                "Dernière visite il y a plus de 18 mois"
            )
        else:
            score += 15
            reasons.append(
                "Dernière visite il y a plus de 12 mois"
            )

        if patient.get("phone"):
            score += 10
            reasons.append("Téléphone disponible")

        score += 15
        reasons.append("Aucun rendez-vous futur")

        score = min(score, 100)

        if score >= 80:
            priority = "high"
        elif score >= 60:
            priority = "medium"
        else:
            priority = "low"

        enriched.append(
            {
                **patient,
                "score": score,
                "priority": priority,
                "reasons": reasons,
                "draft_message": (
                    f"Bonjour {patient.get('patient_name') or ''}, "
                    "le cabinet vous propose un contrôle de suivi. "
                    "Souhaitez-vous prendre rendez-vous ?"
                ),
            }
        )

    enriched.sort(
        key=lambda patient: patient["score"],
        reverse=True,
    )

    return enriched
