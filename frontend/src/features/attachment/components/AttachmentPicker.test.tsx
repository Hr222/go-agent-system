import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AttachmentUploadError, uploadAttachment } from "../api/attachmentApi";
import { AttachmentPicker } from "./AttachmentPicker";

vi.mock("../api/attachmentApi", () => ({
  AttachmentUploadError: class AttachmentUploadError extends Error {
    constructor(message: string, readonly retryable: boolean) {
      super(message);
    }
  },
  uploadAttachment: vi.fn(),
}));

const uploadMock = vi.mocked(uploadAttachment);
const attachment = {
  attachmentId: "a".repeat(32),
  fileName: "source.docx",
  mediaType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  sizeBytes: 64,
  sha256: "b".repeat(64),
  status: "available" as const,
};

afterEach(() => {
  cleanup();
  uploadMock.mockReset();
});

describe("AttachmentPicker", () => {
  it("uploads a selected file, exposes only its reference, and removes it", async () => {
    uploadMock.mockImplementation(async (_file, options) => {
      options?.onProgress?.(50);
      return attachment;
    });
    const onChange = vi.fn();
    const onUploadStateChange = vi.fn();
    render(
      <AttachmentPicker
        value={[]}
        onChange={onChange}
        onUploadStateChange={onUploadStateChange}
      />,
    );

    const file = new File(["document"], "source.docx", { type: attachment.mediaType });
    fireEvent.change(screen.getByLabelText("选择附件"), { target: { files: [file] } });

    await screen.findByText("source.docx");
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([attachment]));
    expect(uploadMock).toHaveBeenCalledWith(
      file,
      expect.objectContaining({ onProgress: expect.any(Function) }),
    );
    expect(onUploadStateChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ status: "uploaded", attachment }),
    ]);

    fireEvent.click(screen.getByRole("button", { name: "移除 source.docx" }));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("shows a failed upload and retries the original file", async () => {
    uploadMock
      .mockRejectedValueOnce(new AttachmentUploadError("附件类型不受支持。", false))
      .mockResolvedValueOnce(attachment);
    const onChange = vi.fn();
    render(<AttachmentPicker value={[]} onChange={onChange} />);
    const file = new File(["bad"], "source.docx", { type: attachment.mediaType });

    fireEvent.change(screen.getByLabelText("选择附件"), { target: { files: [file] } });

    await screen.findByText("上传失败");
    fireEvent.click(screen.getByRole("button", { name: "重新上传 source.docx" }));

    await waitFor(() => expect(onChange).toHaveBeenCalledWith([attachment]));
    expect(uploadMock).toHaveBeenCalledTimes(2);
  });
});
