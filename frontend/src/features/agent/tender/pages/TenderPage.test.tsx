import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { TenderPage } from "./TenderPage";

describe("TenderPage", () => {
  it("keeps Tender as a navigation entry to the controlled chat flow", () => {
    const { container } = render(
      <MemoryRouter>
        <TenderPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "进入对话" }).getAttribute("href")).toBe("/chat");
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(screen.queryByRole("button", { name: "下载" })).toBeNull();
  });
});
