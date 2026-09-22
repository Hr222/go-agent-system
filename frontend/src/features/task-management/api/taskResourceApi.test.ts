import { describe, expect, it, vi } from "vitest";

import { axiosClient } from "../../../services/http/axiosClient";
import { listTaskResources } from "./taskApi";

vi.mock("../../../services/http/axiosClient", () => ({ axiosClient: { get: vi.fn() } }));

it("maps task result resource metadata", async () => {
  vi.mocked(axiosClient.get).mockResolvedValueOnce({ data: {
    task_id: "task-1",
    resources: [{ resource_id: "resource-1", file_name: "skeleton.docx", media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", size_bytes: 12, sha256: "a".repeat(64), download_url: "/api/v1/attachments/resource-1/download" }],
  } });

  await expect(listTaskResources("task-1")).resolves.toEqual([
    expect.objectContaining({ resourceId: "resource-1", fileName: "skeleton.docx", sizeBytes: 12 }),
  ]);
});
