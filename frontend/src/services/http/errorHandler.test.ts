import { describe, expect, it } from "vitest";

import { toApiError } from "./errorHandler";

describe("toApiError", () => {
  it("keeps a controlled message from a structured API detail", () => {
    const error = toApiError({
      isAxiosError: true,
      message: "Request failed with status code 409",
      response: {
        status: 409,
        data: {
          detail: {
            code: "CONVERSATION_PIN_LIMIT_REACHED",
            message: "最多置顶 10 个会话，请先取消一个。",
          },
        },
      },
    });

    expect(error).toEqual({
      message: "最多置顶 10 个会话，请先取消一个。",
      status: 409,
      code: undefined,
    });
  });
});
