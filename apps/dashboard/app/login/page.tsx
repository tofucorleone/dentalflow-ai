import { LoginForm } from "@/components/login-form";
import { getClinicBranding } from "@/lib/server-api";

export default async function LoginPage() {
  const branding = await getClinicBranding();

  return (
    <LoginForm
      displayName={branding.display_name}
      softwareName={branding.software_name}
      logoUrl={branding.logo_url}
    />
  );
}
