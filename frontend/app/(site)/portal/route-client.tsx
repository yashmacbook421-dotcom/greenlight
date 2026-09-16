"use client";

import { AsyncView } from "@/components/async-view";
import { SignInCard } from "@/components/portal-ui";
import { listPortalApplications } from "@/lib/api";
import { useInstaller } from "@/lib/installer";
import { useAsync } from "@/lib/use-async";
import { PortalHomePage } from "@/views/portal-home-view";

export function PortalHomeRoute() {
  const { installer, ready, signIn, signOut } = useInstaller();
  if (!ready) return null;
  if (!installer) return <div className="portal-page narrow"><SignInCard onSignIn={signIn} /></div>;
  return <Applications installer={installer} onSignOut={signOut} />;
}

function Applications({ installer, onSignOut }: { installer: string; onSignOut: () => void }) {
  const state = useAsync(() => listPortalApplications(installer), `portal:${installer}`);
  return (
    <div className="portal-page">
      <AsyncView state={state}>
        {(apps) => <PortalHomePage installer={installer} applications={apps} onSignOut={onSignOut} />}
      </AsyncView>
    </div>
  );
}
