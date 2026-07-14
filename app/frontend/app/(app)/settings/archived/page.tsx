import type { Metadata } from "next";

import { ArchivedContractsPage } from "@/src/screens/ArchivedContractsPage";

export const metadata: Metadata = { title: "Archived" };

export default function Page() {
  return <ArchivedContractsPage />;
}
