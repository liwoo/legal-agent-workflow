import type { Metadata } from "next";

import { ReferencePage } from "@/src/screens/ReferencePage";

export const metadata: Metadata = { title: "How it works" };

export default function Page() {
  return <ReferencePage />;
}
