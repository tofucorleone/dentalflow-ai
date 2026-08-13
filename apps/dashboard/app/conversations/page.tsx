import { MessageSquareText } from "lucide-react";

import {
  ConversationInbox,
  type ConversationThreadListResponse,
} from "@/components/conversation-inbox";
import { PageHeader } from "@/components/page-header";
import { backendFetch } from "@/lib/server-api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

async function getInitialConversations(): Promise<ConversationThreadListResponse> {
  const response = await backendFetch(
    "/conversations?limit=50&offset=0&status=open",
  );

  if (!response.ok) {
    throw new Error(
      `API ${response.status}: ${await response.text()}`,
    );
  }

  return response.json() as Promise<ConversationThreadListResponse>;
}

export default async function ConversationsPage() {
  const conversations = await getInitialConversations();

  return (
    <>
      <div className="inbox-page-heading">
        <PageHeader
          title="Conversations"
          description="Messages patients, historique omnicanal et état de prise en charge."
        />

        <div className="inbox-readonly-badge">
          <MessageSquareText size={16} />
          Lecture seule
        </div>
      </div>

      <ConversationInbox initialData={conversations} />
    </>
  );
}
