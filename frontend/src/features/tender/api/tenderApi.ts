import { axiosClient } from "../../../services/http/axiosClient";

export type TenderSourceEvidence = {
  evidence_id: string;
  location: string;
  quote: string;
  page_no: number | null;
  section_title: string | null;
};

export type TenderRequirement = {
  requirement_id: string;
  title: string;
  kind: string;
  required: boolean;
  output_slug: string | null;
  evidence_refs: string[];
  notes: string[];
};

export type TenderOutputPlan = {
  name: string;
  slug: string;
  document_label: string;
  purpose: string | null;
  section_titles: string[];
  requirement_refs: string[];
  evidence_refs: string[];
};

export type TenderAnalysis = {
  status: "completed" | "needs_review";
  package_type: "single_volume" | "multi_volume" | "uncertain";
  summary: string;
  key_requirements: TenderRequirement[];
  outputs: TenderOutputPlan[];
  evidence: TenderSourceEvidence[];
  uncertainties: string[];
  risks: string[];
};

export type TenderArtifact = {
  file_name: string;
  media_type: string;
  size_bytes: number;
  content_base64: string;
};

export type TenderSkeletonResult = {
  analysis: TenderAnalysis;
  artifacts: TenderArtifact[];
  model: string;
  prompt_version: string;
};

export type TenderApiError = {
  code: string;
  message: string;
};

export async function generateTenderSkeleton(
  file: File,
  userFocus: string,
): Promise<TenderSkeletonResult> {
  const formData = new FormData();
  formData.append("file", file);
  if (userFocus.trim()) formData.append("user_focus", userFocus.trim());

  const response = await axiosClient.post<TenderSkeletonResult>(
    "/v1/agents/tender/skeleton",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return response.data;
}
