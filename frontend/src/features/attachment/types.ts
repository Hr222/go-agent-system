export type AttachmentRef = {
  attachmentId: string;
  fileName: string;
  mediaType: string;
  sizeBytes: number;
  sha256: string;
  status: "available";
};

export type AttachmentUploadStatus = "selected" | "uploading" | "uploaded" | "failed";

export type AttachmentUploadItem = {
  localId: string;
  file: File;
  status: AttachmentUploadStatus;
  progress: number;
  attachment?: AttachmentRef;
  error?: string;
};

export type AttachmentPickerProps = {
  value: readonly AttachmentRef[];
  onChange: (attachments: AttachmentRef[]) => void;
  onUploadStateChange?: (items: readonly AttachmentUploadItem[]) => void;
  conversationId?: string;
  accept?: string;
  maxCount?: number;
  disabled?: boolean;
  layout?: "default" | "composer";
};

export type AttachmentUploadOptions = {
  conversationId?: string;
  signal?: AbortSignal;
  onProgress?: (progress: number) => void;
};
