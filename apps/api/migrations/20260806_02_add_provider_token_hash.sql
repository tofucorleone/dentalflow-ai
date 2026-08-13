BEGIN;

ALTER TABLE clinic_integrations
ADD COLUMN IF NOT EXISTS provider_token_hash TEXT;

ALTER TABLE clinic_integrations
DROP CONSTRAINT IF EXISTS
clinic_integrations_provider_token_hash_format;

ALTER TABLE clinic_integrations
ADD CONSTRAINT clinic_integrations_provider_token_hash_format
CHECK (
    provider_token_hash IS NULL
    OR provider_token_hash ~ '^[0-9a-f]{64}$'
);

COMMENT ON COLUMN clinic_integrations.provider_token_hash IS
'Empreinte SHA-256 du token fourni par le webhook; le token brut ne doit jamais être stocké.';

COMMIT;
