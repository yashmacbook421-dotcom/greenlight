"use client";

import { AsyncView } from "@/components/async-view";
import { getPortalApplication } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { PortalApplicationPage } from "@/views/portal-application-view";

export function PortalApplicationRoute({ id }: { id: string }) {
  const state = useAsync(() => getPortalApplication(id), id);
  return (
    <div className="portal-page">
      <AsyncView state={state}>{(app) => <PortalApplicationPage key={app.id} initial={app} />}</AsyncView>
    </div>
  );
}
