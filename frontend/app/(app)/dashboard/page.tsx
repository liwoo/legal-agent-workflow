import type { Metadata } from "next";

import { DashboardPage } from "@/src/screens/DashboardPage";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <DashboardPage />;
}
