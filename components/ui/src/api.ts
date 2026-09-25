export type ChatResponse = {
  role: string;
  trip_id: string;
  content: string;
  grounded?: boolean;
  error?: string;
};

export async function postChat(body: object): Promise<ChatResponse> {
  const response = await fetch("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await response.json()) as ChatResponse;
  if (!response.ok) {
    throw new Error(payload.error || "The response agent rejected the request.");
  }
  return payload;
}
