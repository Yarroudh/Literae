import { ResearchChat } from "@/components/research/research-chat";
import { OfflinePage } from "@/components/offline/offline-page";

export const dynamic = "force-dynamic";

export default function Home() {
  if (process.env.OFFLINE?.trim().toLowerCase() === "true") {
    return <OfflinePage />;
  }

  return <ResearchChat />;
}
