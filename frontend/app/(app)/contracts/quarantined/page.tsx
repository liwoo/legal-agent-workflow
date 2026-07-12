import type { Metadata } from "next";

import { ContractsQueuePage } from "@/src/screens/ContractsQueuePage";

export const metadata: Metadata = { title: "Quarantined" };

export default function Page() {
  return <ContractsQueuePage queue="quarantined" />;
}
