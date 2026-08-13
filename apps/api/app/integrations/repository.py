async def get_active_integration(
    *,
    cur,
    provider: str,
    provider_instance: str,
) -> dict | None:
    await cur.execute(
        """
        SELECT
            id,
            clinic_id,
            provider,
            provider_instance,
            phone_number,
            api_base_url,
            secret_reference,
            provider_token_hash,
            configuration,
            active,
            created_at,
            updated_at
        FROM clinic_integrations
        WHERE LOWER(BTRIM(provider)) = LOWER(BTRIM(%s))
          AND BTRIM(provider_instance) = BTRIM(%s)
          AND active = TRUE
        LIMIT 1
        """,
        (
            provider,
            provider_instance,
        ),
    )

    return await cur.fetchone()


__all__ = ["get_active_integration"]
