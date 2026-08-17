import { appConfig } from "../../../app/appConfig";
import { axiosClient } from "../../../services/http/axiosClient";
import { toApiError } from "../../../services/http/errorHandler";

import { knowledgeBaseMockApi } from "./knowledgeBaseMockApi";
import type {
  KnowledgeBaseOverview,
  KnowledgeDocumentPage,
  KnowledgeIngestResult,
  KnowledgeDocument,
  KnowledgeSearchResponse,
  KnowledgeRetrievalMode,
  KnowledgeUploadPreview,
  KnowledgeDocumentFileType,
  ListKnowledgeDocumentsParams,
  UploadDocumentRequest,
} from "../types";

const useMock = appConfig.knowledgeBaseDataSource === "mock";

export function getKnowledgeDocumentPreviewUrl(documentId: number): string | undefined {
  if (useMock) return undefined;
  const baseUrl = appConfig.apiBaseUrl.replace(/\/$/, "");
  return `${baseUrl}/v1/kb/management/documents/${documentId}/content`;
}

type ApiManagementOverview = {
  document_count: number;
  chunk_count: number;
  pending_count: number;
  failed_count: number;
  latest_updated_at: string | null;
};

type ApiManagementDocument = {
  document_id: number;
  policy_name: string;
  policy_category: string;
  responsible_department: string | null;
  file_name: string | null;
  file_type: string | null;
  file_size_bytes: number | null;
  version_id: number | null;
  version_label: string | null;
  processing_status: KnowledgeDocument["status"];
  processing_progress: number | null;
  publication_status: string | null;
  parser_status: string | null;
  section_count: number;
  chunk_count: number;
  updated_at: string | null;
  updated_by: string | null;
  error_message: string | null;
  source_path?: string | null;
  page_count?: number | null;
  parse_method?: string | null;
  is_scanned?: boolean | null;
  created_at?: string | null;
};

type ApiUploadPreview = {
  upload_id: string;
  policy_name_guess: string | null;
  derived_version_label: string | null;
  registered_file: {
    file_name: string;
    size_bytes: number;
  } | null;
  validation: {
    is_allowed: boolean;
    warnings: string[];
  } | null;
  section_result: { total_sections: number } | null;
  chunk_result: { total_chunks: number } | null;
};

type ApiPipelineResponse = {
  persistence: {
    persisted: boolean;
    document_id: number | null;
    version_id: number | null;
    version_label: string | null;
    chunk_count: number;
  } | null;
};

type ApiRetrievalHit = {
  document_id: number;
  chunk_id: number;
  policy_name: string;
  policy_category: string;
  version_label: string;
  section_title: string | null;
  section_path: string | null;
  page_no: number | null;
  chunk_text: string;
  score: number;
  retrieval_source: string;
  file_name: string | null;
};

type ApiSearchResponse = {
  query: string;
  hits: ApiRetrievalHit[];
  debug: {
    strategy: string;
    stages: Array<{
      name: string;
      source: string | null;
      input_count: number | null;
      output_count: number | null;
    }>;
  };
};

function formatBytes(value: number | null): string {
  if (value === null || value < 0) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
}

function mapDocument(document: ApiManagementDocument): KnowledgeDocument {
  const normalizedType = (document.file_type ?? "").replace(".", "").toUpperCase();
  const typeByExtension: Record<string, KnowledgeDocumentFileType> = {
    PDF: "PDF",
    DOCX: "DOCX",
    DOC: "DOC",
    XLSX: "XLSX",
    XLS: "XLS",
    JPG: "JPG",
    JPEG: "JPG",
    PNG: "PNG",
    BMP: "BMP",
    TIF: "TIF",
    TIFF: "TIF",
    WEBP: "WEBP",
  };
  const type = typeByExtension[normalizedType] ?? "FILE";

  return {
    id: document.document_id,
    name: document.file_name ?? document.policy_name,
    type,
    size: formatBytes(document.file_size_bytes),
    category: document.policy_category,
    version: document.version_label ?? "—",
    status: document.processing_status,
    progress: document.processing_progress ?? undefined,
    chunks: document.chunk_count,
    updatedAt: formatDate(document.updated_at),
    updatedBy: document.updated_by ?? "—",
    error: document.error_message ?? undefined,
  };
}

function mapOverview(overview: ApiManagementOverview): KnowledgeBaseOverview {
  const completedCount = Math.max(
    overview.document_count - overview.pending_count - overview.failed_count,
    0,
  );
  const retrievalAvailability = overview.document_count === 0
    ? 0
    : Number(((completedCount / overview.document_count) * 100).toFixed(1));

  return {
    documentCount: overview.document_count,
    chunkCount: overview.chunk_count,
    retrievalAvailability,
    pendingCount: overview.pending_count,
    failedCount: overview.failed_count,
    updatedAt: formatDate(overview.latest_updated_at),
  };
}

function managementRequestParams(params: ListKnowledgeDocumentsParams) {
  return {
    document_name: params.search?.trim() || undefined,
    policy_category: params.category || undefined,
    status: params.statuses?.length ? params.statuses : undefined,
    limit: params.limit,
    offset: params.offset,
  };
}

function mapUploadPreview(preview: ApiUploadPreview, category: string): KnowledgeUploadPreview {
  return {
    uploadId: preview.upload_id,
    fileName: preview.registered_file?.file_name ?? preview.policy_name_guess ?? "未命名文件",
    category,
    policyNameGuess: preview.policy_name_guess ?? undefined,
    versionLabel: preview.derived_version_label ?? undefined,
    fileSizeBytes: preview.registered_file?.size_bytes,
    isAllowed: preview.validation?.is_allowed ?? true,
    warnings: preview.validation?.warnings ?? [],
    sectionCount: preview.section_result?.total_sections ?? 0,
    chunkCount: preview.chunk_result?.total_chunks ?? 0,
  };
}

function mapPipelineResult(response: ApiPipelineResponse): KnowledgeIngestResult {
  return {
    documentId: response.persistence?.document_id ?? undefined,
    versionId: response.persistence?.version_id ?? undefined,
    versionLabel: response.persistence?.version_label ?? undefined,
    chunkCount: response.persistence?.chunk_count ?? 0,
    persisted: response.persistence?.persisted ?? false,
  };
}

export async function getKnowledgeBaseOverview(): Promise<KnowledgeBaseOverview> {
  if (useMock) return knowledgeBaseMockApi.getOverview();
  try {
    const response = await axiosClient.get<ApiManagementOverview>("/v1/kb/management/overview");
    return mapOverview(response.data);
  } catch (error) {
    throw toApiError(error);
  }
}

export async function listKnowledgeDocuments(params: ListKnowledgeDocumentsParams): Promise<KnowledgeDocumentPage> {
  if (useMock) return knowledgeBaseMockApi.listDocumentsPage(params);
  try {
    const response = await axiosClient.get<{ items: ApiManagementDocument[]; total_count: number }>(
      "/v1/kb/management/documents",
      {
        params: {
          ...managementRequestParams(params),
          limit: params.limit ?? 10,
          offset: params.offset ?? 0,
        },
        paramsSerializer: { indexes: null },
      },
    );
    return {
      items: response.data.items.map(mapDocument),
      totalCount: response.data.total_count,
    };
  } catch (error) {
    throw toApiError(error);
  }
}

export async function listRecentKnowledgeDocuments(
  params: ListKnowledgeDocumentsParams,
): Promise<KnowledgeDocument[]> {
  if (useMock) {
    return knowledgeBaseMockApi.listRecentDocuments(params);
  }
  try {
    const response = await axiosClient.get<{ items: ApiManagementDocument[]; total_count: number }>(
      "/v1/kb/management/recent-documents",
      {
        params: {
          ...managementRequestParams(params),
          limit: params.limit ?? 6,
        },
        paramsSerializer: { indexes: null },
      },
    );
    return response.data.items.map(mapDocument);
  } catch (error) {
    throw toApiError(error);
  }
}

export async function listKnowledgeBaseCategories(): Promise<string[]> {
  if (useMock) return knowledgeBaseMockApi.listCategories();
  try {
    const response = await axiosClient.get<{ items: string[] }>("/v1/kb/management/categories");
    return response.data.items;
  } catch (error) {
    throw toApiError(error);
  }
}

export async function getKnowledgeDocumentDetail(documentId: number): Promise<KnowledgeDocument> {
  if (useMock) {
    const documents = await knowledgeBaseMockApi.listDocuments({});
    const document = documents.find((item) => item.id === documentId);
    if (!document) throw new Error("文档不存在或已被删除。");
    return document;
  }
  try {
    const response = await axiosClient.get<ApiManagementDocument>(
      `/v1/kb/management/documents/${documentId}`,
    );
    return mapDocument(response.data);
  } catch (error) {
    throw toApiError(error);
  }
}

export async function previewKnowledgeDocument(
  request: UploadDocumentRequest,
): Promise<KnowledgeUploadPreview> {
  if (useMock) return knowledgeBaseMockApi.previewUpload(request);
  try {
    const formData = new FormData();
    formData.append("file", request.file);
    formData.append("policy_category", request.category);
    const response = await axiosClient.post<ApiUploadPreview>(
      "/v1/kb/policy-pipeline/preview-upload",
      formData,
    );
    return mapUploadPreview(response.data, request.category);
  } catch (error) {
    throw toApiError(error);
  }
}

export async function ingestKnowledgeDocument(
  preview: KnowledgeUploadPreview,
): Promise<KnowledgeIngestResult> {
  if (useMock) return knowledgeBaseMockApi.ingestUpload(preview);
  try {
    const response = await axiosClient.post<ApiPipelineResponse>(
      "/v1/kb/policy-pipeline/ingest-upload",
      {
        upload_id: preview.uploadId,
        policy_category: preview.category,
        version_label: preview.versionLabel,
      },
    );
    return mapPipelineResult(response.data);
  } catch (error) {
    throw toApiError(error);
  }
}

export async function activateKnowledgeDocument(
  result: KnowledgeIngestResult,
): Promise<void> {
  if (!result.documentId || !result.versionId) return;
  if (useMock) {
    await knowledgeBaseMockApi.activatePublication(result.documentId, result.versionId);
    return;
  }
  try {
    await axiosClient.post("/v1/kb/publication/activate", {
      document_id: result.documentId,
      version_id: result.versionId,
    });
  } catch (error) {
    throw toApiError(error);
  }
}

export async function retryKnowledgeDocument(documentId: number): Promise<KnowledgeIngestResult> {
  if (useMock) {
    const document = await knowledgeBaseMockApi.retryDocument(documentId);
    return {
      documentId: document.id,
      versionId: document.id,
      versionLabel: document.version,
      chunkCount: document.chunks,
      persisted: true,
    };
  }
  try {
    const response = await axiosClient.post<ApiPipelineResponse>(
      `/v1/kb/documents/${documentId}/retry`,
    );
    return mapPipelineResult(response.data);
  } catch (error) {
    throw toApiError(error);
  }
}

export async function searchKnowledgeBase(
  query: string,
  retrievalMode: KnowledgeRetrievalMode = "hybrid",
  topK = 5,
): Promise<KnowledgeSearchResponse> {
  if (useMock) return knowledgeBaseMockApi.search(query, topK);
  try {
    const response = await axiosClient.post<ApiSearchResponse>("/v1/kb/retrieval/search", {
      query,
      top_k: topK,
      retrieval_mode: retrievalMode,
    });
    return {
      query: response.data.query,
      strategy: response.data.debug.strategy,
      stages: response.data.debug.stages.map((stage) => ({
        name: stage.name,
        source: stage.source,
        inputCount: stage.input_count,
        outputCount: stage.output_count,
      })),
      results: response.data.hits.map((hit) => ({
        id: hit.chunk_id,
        title: hit.section_title ?? hit.policy_name,
        source: hit.file_name ?? hit.policy_name,
        section: hit.section_path ?? hit.section_title ?? "—",
        page: hit.page_no === null ? "—" : `第 ${hit.page_no} 页`,
        score: hit.score,
        text: hit.chunk_text,
        tags: [hit.policy_category, hit.retrieval_source],
      })),
    };
  } catch (error) {
    throw toApiError(error);
  }
}
