import { redirect } from "next/navigation";

// Applications now start in the applicant portal.
export default function NewApplication() {
  redirect("/portal/new");
}
