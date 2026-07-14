import type { Metadata } from "next";

import { PlaybookPage } from "@/src/screens/PlaybookPage";

export const metadata: Metadata = { title: "Playbook" };

export default function Page() {
  return <PlaybookPage />;
}
