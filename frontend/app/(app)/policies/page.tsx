import type { Metadata } from "next";

import { PoliciesPage } from "@/src/screens/PoliciesPage";

export const metadata: Metadata = { title: "Policies" };

export default function Page() {
  return <PoliciesPage />;
}
