import type { Metadata } from "next";

import { ContractsQueuePage } from "@/src/screens/ContractsQueuePage";

export const metadata: Metadata = { title: "Pending" };

export default function Page() {
  return <ContractsQueuePage queue="pending" />;
}
