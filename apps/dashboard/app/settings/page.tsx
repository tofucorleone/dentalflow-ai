import { ClinicBrandingForm } from "@/components/clinic-branding-form";
import { ConversationHistoryClearButton } from "@/components/conversation-history-clear-button";
import { PageHeader } from "@/components/page-header";
import { getClinicBranding } from "@/lib/server-api";

export default async function SettingsPage() {
  const branding = await getClinicBranding();

  return (
    <>
      <PageHeader
        title="Paramètres"
        description="Configuration de la clinique."
      />

      <section className="panel settings-panel">
        <div className="settings-heading">
          <h2>Identité de la clinique</h2>
          <p>
            Personnalisez les noms affichés dans l’interface.
          </p>
        </div>

        <ClinicBrandingForm
          initialDisplayName={branding.display_name}
          initialSoftwareName={branding.software_name}
          initialCurrencyLabel={branding.currency_label}
          initialPrimaryColor={branding.primary_color}
        />
      </section>

      <section className="panel settings-panel">
        <div className="settings-heading">
          <h2>Historique des conversations</h2>
          <p>
            Supprime les conversations, messages et états
            conversationnels de cette clinique. Les patients,
            rendez-vous et données métier sont conservés.
          </p>
        </div>

        <ConversationHistoryClearButton />
      </section>
    </>
  );
}
