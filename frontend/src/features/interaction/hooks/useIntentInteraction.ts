import { useMutation } from "@tanstack/react-query";

import { recognizeIntent, respondToIntentProposal } from "../api/interactionApi";

export function useIntentRecognition() {
  return useMutation({ mutationFn: recognizeIntent });
}

export function useIntentProposalResponse() {
  return useMutation({
    mutationFn: ({ proposalId, action }: { proposalId: string; action: "confirm" | "cancel" }) => (
      respondToIntentProposal(proposalId, action)
    ),
  });
}
