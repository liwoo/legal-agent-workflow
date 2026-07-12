import type { Metadata } from "next";

import { ContractsQueuePage } from "@/src/screens/ContractsQueuePage";

export const metadata: Metadata = { title: "Approved" };

export default function Page() {
  return <ContractsQueuePage queue="approved" />;
}
