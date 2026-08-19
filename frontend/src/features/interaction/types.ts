export type InteractionStatus =
  | "needs_clarification"
  | "unrecognized"
  | "pending"
  | "cancelled"
  | "completed"
  | "rejected"
  | "failed";

export type InteractionStreamApproval = {
  proposalId: string;
  state: "pending" | "confirmed" | "cancelled";
  summary: string;
  confirmationPrompt: string;
  conversationId?: string;
};

export type InteractionStreamResult = {
  status: Exclude<InteractionStatus, "pending" | "completed">;
  message: string;
  errorCode: string | null;
};

export type InteractionStreamMeta = {
  requestId: string;
  model: string;
  promptVersion: string;
};

export type InteractionStreamComplete = InteractionStreamMeta & {
  usage: {
    input_tokens?: number | null;
    output_tokens?: number | null;
    total_tokens?: number | null;
  };
};

export type InteractionStreamHandlers = {
  onMeta?: (meta: InteractionStreamMeta) => void;
  onDelta?: (content: string) => void;
  onComplete?: (complete: InteractionStreamComplete) => void;
  onApprovalRequired?: (approval: InteractionStreamApproval) => void;
  onResult?: (result: InteractionStreamResult) => void;
};

export type IntentAssessment = {
  status: "matched" | "needs_clarification" | "unrecognized";
  capability_code: string | null;
  missing_fields: string[];
  clarification: string | null;
  confidence: number | null;
  error_code: string | null;
};

export type InteractionProposal = {
  proposal_id: string;
  state: "pending" | "confirmed" | "cancelled";
  capability_code: string;
  summary: string;
  confirmation_prompt: string;
};

export type InteractionGatewayResult = {
  status: InteractionStatus;
  message: string;
  assessment: IntentAssessment | null;
  proposal: InteractionProposal | null;
  execution_result: Record<string, unknown> | null;
  error_code: string | null;
  conversation_id?: string | null;
};

export type IntentRecognitionInput = {
  userInput: string;
  providedInputs: Record<string, unknown>;
};
