import axios from "axios";

import { axiosClient } from "../../../services/http/axiosClient";

import type { AttachmentRef, AttachmentUploadOptions } from "../types";

type AttachmentUploadResponse = {
  attachment_id: string;
  file_name: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  status: string;
};

export class AttachmentUploadError extends Error {
  constructor(message: string, readonly retryable: boolean) {
    super(message);
    this.name = "AttachmentUploadError";
  }
}

export async function uploadAttachment(
  file: File,
  { conversationId, signal, onProgress }: AttachmentUploadOptions = {},
): Promise<AttachmentRef> {
  const formData = new FormData();
  formData.set("file", file);
  if (conversationId) formData.set("conversation_id", conversationId);

  try {
    const response = await axiosClient.post<AttachmentUploadResponse>(
      "/v1/attachments/upload",
      formData,
      {
        signal,
        onUploadProgress: (event) => {
          if (!event.total) return;
          onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
        },
      },
    );
    return toAttachmentRef(response.data);
  } catch (error) {
    throw toAttachmentUploadError(error);
  }
}

function toAttachmentRef(response: AttachmentUploadResponse): AttachmentRef {
  if (
    response.status !== "available"
    || !response.attachment_id
    || !response.file_name
    || !response.media_type
    || !response.sha256
    || response.size_bytes < 1
  ) {
    throw new AttachmentUploadError("附件上传响应无效。", false);
  }
  return {
    attachmentId: response.attachment_id,
    fileName: response.file_name,
    mediaType: response.media_type,
    sizeBytes: response.size_bytes,
    sha256: response.sha256,
    status: "available",
  };
}

function toAttachmentUploadError(error: unknown): AttachmentUploadError {
  if (error instanceof AttachmentUploadError) return error;
  if (axios.isAxiosError(error)) {
    const message = responseErrorMessage(error.response?.data) ?? error.message;
    return new AttachmentUploadError(
      message || "附件上传失败，请重试。",
      !error.response || error.response.status >= 500,
    );
  }
  return new AttachmentUploadError(
    error instanceof Error && error.message ? error.message : "附件上传失败，请重试。",
    true,
  );
}

function responseErrorMessage(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const detail = "detail" in data ? data.detail : null;
  if (!detail || typeof detail !== "object") return null;
  const message = "message" in detail ? detail.message : null;
  return typeof message === "string" && message.trim() ? message : null;
}
