BEGIN;

CREATE TABLE IF NOT EXISTS clinic_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    clinic_id UUID NOT NULL
        REFERENCES clinics(id)
        ON DELETE CASCADE,

    provider TEXT NOT NULL,
    provider_instance TEXT NOT NULL,
    phone_number TEXT,

    api_base_url TEXT,
    secret_reference TEXT,

    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT clinic_integrations_provider_not_blank
        CHECK (BTRIM(provider) <> ''),

    CONSTRAINT clinic_integrations_instance_not_blank
        CHECK (BTRIM(provider_instance) <> ''),

    CONSTRAINT clinic_integrations_provider_instance_unique
        UNIQUE (provider, provider_instance),

    CONSTRAINT clinic_integrations_clinic_provider_instance_unique
        UNIQUE (clinic_id, provider, provider_instance)
);

CREATE INDEX IF NOT EXISTS
    clinic_integrations_clinic_active_idx
ON clinic_integrations (
    clinic_id,
    active
);

CREATE INDEX IF NOT EXISTS
    clinic_integrations_provider_active_idx
ON clinic_integrations (
    provider,
    active
);

COMMENT ON TABLE clinic_integrations IS
'Intégrations externes configurées séparément pour chaque clinique.';

COMMENT ON COLUMN clinic_integrations.provider_instance IS
'Identifiant d’instance envoyé par le fournisseur, par exemple agence.';

COMMENT ON COLUMN clinic_integrations.phone_number IS
'Numéro de la clinique connecté au fournisseur, jamais le numéro patient.';

COMMENT ON COLUMN clinic_integrations.secret_reference IS
'Référence vers un secret externe ou une variable sécurisée; ne pas stocker la clé API en clair.';

COMMIT;
