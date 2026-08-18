import { axiosClient } from "../../../services/http/axiosClient";
import { toApiError } from "../../../services/http/errorHandler";
import { appConfig } from "../../../app/appConfig";

import type { IntentRecognitionInput, InteractionGatewayResult } from "../types";

export async function recognizeIntent(
  input: IntentRecognitionInput,
): Promise<InteractionGatewayResult> {
  try {
    const response = await axiosClient.post<InteractionGatewayResult>(
      "/v1/interaction/intent",
      {
        user_input: input.userInput,
        provided_inputs: input.providedInputs,
      },
      { timeout: appConfig.llmRequestTimeoutMs },
    );
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}

export async function respondToIntentProposal(
  proposalId: string,
  action: "confirm" | "cancel",
): Promise<InteractionGatewayResult> {
  try {
    const response = await axiosClient.post<InteractionGatewayResult>(
      `/v1/interaction/proposals/${encodeURIComponent(proposalId)}/confirmation`,
      { action },
      { timeout: appConfig.llmRequestTimeoutMs },
    );
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}
