import { afterEach, describe, expect, it, vi } from "vitest";

import { axiosClient } from "../../../services/http/axiosClient";
import { AttachmentUploadError, uploadAttachment } from "./attachmentApi";

vi.mock("../../../services/http/axiosClient", () => ({
  axiosClient: { post: vi.fn() },
}));

const postMock = vi.mocked(axiosClient.post);

afterEach(() => {
  postMock.mockReset();
});

describe("uploadAttachment", () => {
  it("uploads a file and maps the server response to a safe dynamic reference", async () => {
    postMock.mockImplementation(async (_path, _body, options) => {
      options?.onUploadProgress?.({
        loaded: 32,
        total: 64,
        bytes: 32,
        lengthComputable: true,
      });
      return {
        data: {
          attachment_id: "a".repeat(32),
          file_name: "source.docx",
          media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          size_bytes: 64,
          sha256: "b".repeat(64),
          status: "available",
        },
      };
    });
    const progress = vi.fn();
    const file = new File(["document"], "source.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    const attachment = await uploadAttachment(file, {
      conversationId: "00000000-0000-0000-0000-000000000001",
      onProgress: progress,
    });

    expect(attachment).toEqual({
      attachmentId: "a".repeat(32),
      fileName: "source.docx",
      mediaType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      sizeBytes: 64,
      sha256: "b".repeat(64),
      status: "available",
    });
    expect(progress).toHaveBeenCalledWith(50);
    expect(postMock).toHaveBeenCalledWith(
      "/v1/attachments/upload",
      expect.any(FormData),
      expect.objectContaining({ onUploadProgress: expect.any(Function) }),
    );
    const formData = postMock.mock.calls[0]?.[1] as FormData;
    expect(formData.get("file")).toBe(file);
    expect(formData.get("conversation_id")).toBe("00000000-0000-0000-0000-000000000001");
  });

  it("turns a server validation error into a non-retryable controlled error", async () => {
    postMock.mockRejectedValue({
      isAxiosError: true,
      message: "Request failed",
      response: {
        status: 400,
        data: { detail: { code: "INVALID_INPUT", message: "附件类型不受支持。" } },
      },
    });

    await expect(uploadAttachment(new File(["bad"], "bad.exe"))).rejects.toEqual(
      new AttachmentUploadError("附件类型不受支持。", false),
    );
  });
});
