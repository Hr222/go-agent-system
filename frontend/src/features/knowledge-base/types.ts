export type KnowledgeDocumentStatus = "ready" | "processing" | "failed";

export type KnowledgeRetrievalMode = "exact" | "hnsw" | "hybrid";

export type KnowledgeDocumentFileType =
  | "PDF"
  | "DOCX"
  | "DOC"
  | "XLSX"
  | "XLS"
  | "JPG"
  | "PNG"
  | "BMP"
  | "TIF"
  | "WEBP"
  | "FILE";

export type KnowledgeDocument = {
  id: number;
  name: string;
  type: KnowledgeDocumentFileType;
  size: string;
  category: string;
  version: string;
  status: KnowledgeDocumentStatus;
  progress?: number;
  chunks: number;
  updatedAt: string;
  updatedBy: string;
  error?: string;
};

export type KnowledgeBaseOverview = {
  documentCount: number;
  chunkCount: number;
  retrievalAvailability: number;
  pendingCount: number;
  failedCount: number;
  updatedAt: string;
};

export type ListKnowledgeDocumentsParams = {
  search?: string;
  statuses?: KnowledgeDocumentStatus[];
  category?: string;
  limit?: number;
  offset?: number;
};

export type KnowledgeDocumentPage = {
  items: KnowledgeDocument[];
  totalCount: number;
};

export type UploadDocumentRequest = {
  file: File;
  category: string;
};

export type KnowledgeUploadPreview = {
  uploadId: string;
  fileName: string;
  category: string;
  policyNameGuess?: string;
  versionLabel?: string;
  fileSizeBytes?: number;
  isAllowed: boolean;
  warnings: string[];
  sectionCount: number;
  chunkCount: number;
};

export type KnowledgeIngestResult = {
  documentId?: number;
  versionId?: number;
  versionLabel?: string;
  chunkCount: number;
  persisted: boolean;
};

export type RetrievalResult = {
  id: number;
  title: string;
  source: string;
  section: string;
  page: string;
  score: number;
  text: string;
  tags: string[];
};

export type KnowledgeSearchResponse = {
  query: string;
  results: RetrievalResult[];
  strategy: string;
  stages: KnowledgeRetrievalStage[];
};

export type KnowledgeRetrievalStage = {
  name: string;
  source: string | null;
  inputCount: number | null;
  outputCount: number | null;
};
