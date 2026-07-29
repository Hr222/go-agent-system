import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDeltaRenderQueue } from "./useDeltaRenderQueue";

type FrameCallback = FrameRequestCallback;

let frameCallbacks = new Map<number, FrameCallback>();
let nextFrameId = 1;

beforeEach(() => {
  frameCallbacks = new Map();
  nextFrameId = 1;
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameCallback) => {
    const frameId = nextFrameId;
    nextFrameId += 1;
    frameCallbacks.set(frameId, callback);
    return frameId;
  }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn((frameId: number) => frameCallbacks.delete(frameId)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useDeltaRenderQueue", () => {
  it("以受控节奏按顺序提交增量，并在完成前排空队列", async () => {
    const rendered: string[] = [];
    const settled = vi.fn();
    const { result } = renderHook(() => useDeltaRenderQueue());

    act(() => {
      result.current.start((delta) => rendered.push(delta));
      result.current.enqueue("你");
      result.current.enqueue("好");
      result.current.settle(settled);
    });

    expect(rendered).toEqual([]);
    expect(result.current.isRendering).toBe(true);

    await runNextFrame(0);
    expect(rendered).toEqual(["你"]);
    expect(settled).not.toHaveBeenCalled();

    await runNextFrame(32);
    expect(rendered).toEqual(["你", "好"]);
    expect(settled).not.toHaveBeenCalled();

    await runNextFrame(48);
    expect(settled).toHaveBeenCalledOnce();
    expect(result.current.isRendering).toBe(false);
  });

  it("取消或失败时也会在排空已接收内容后结束", async () => {
    const rendered: string[] = [];
    const settled = vi.fn();
    const { result } = renderHook(() => useDeltaRenderQueue());

    act(() => {
      result.current.start((delta) => rendered.push(delta));
      result.current.enqueue("部分内容");
      result.current.settle(settled);
    });

    for (let timestamp = 0; frameCallbacks.size > 0; timestamp += 32) {
      await runNextFrame(timestamp);
    }

    expect(rendered.join("")).toBe("部分内容");
    expect(settled).toHaveBeenCalledOnce();
  });

  it("无增量的终止状态也会保留请求锁直到下一帧", async () => {
    const settled = vi.fn();
    const { result } = renderHook(() => useDeltaRenderQueue());

    act(() => {
      result.current.start(vi.fn());
      result.current.settle(settled);
    });

    expect(result.current.isRendering).toBe(true);
    await runNextFrame(0);
    expect(settled).not.toHaveBeenCalled();
    await runNextFrame(16);
    expect(settled).toHaveBeenCalledOnce();
    expect(result.current.isRendering).toBe(false);
  });

  it("保持中英文与 Emoji 字素簇顺序，并分多个绘制时机显示", async () => {
    const rendered: string[] = [];
    const { result } = renderHook(() => useDeltaRenderQueue());

    act(() => {
      result.current.start((delta) => rendered.push(delta));
      result.current.enqueue("A👩🏽‍💻你");
    });

    await runNextFrame(0);
    await runNextFrame(32);
    await runNextFrame(64);

    expect(rendered).toEqual(["A", "👩🏽‍💻", "你"]);
    expect(rendered.join("")).toBe("A👩🏽‍💻你");
  });

  it("在大量积压时增加每次提交量并保持最终顺序", async () => {
    const rendered: string[] = [];
    const { result } = renderHook(() => useDeltaRenderQueue());
    const content = "你".repeat(96);

    act(() => {
      result.current.start((delta) => rendered.push(delta));
      result.current.enqueue(content);
    });

    await runNextFrame(0);
    expect(rendered[0]).toHaveLength(3);

    for (let timestamp = 32; frameCallbacks.size > 0; timestamp += 32) {
      await runNextFrame(timestamp);
    }

    expect(rendered.join("")).toBe(content);
    expect(rendered.length).toBeLessThanOrEqual(32);
  });

  it("卸载后取消待执行的旧队列回调", () => {
    const rendered = vi.fn();
    const { result, unmount } = renderHook(() => useDeltaRenderQueue());

    act(() => {
      result.current.start(rendered);
      result.current.enqueue("旧内容");
    });
    unmount();

    expect(frameCallbacks.size).toBe(0);
    expect(rendered).not.toHaveBeenCalled();
  });
});

async function runNextFrame(timestamp: number): Promise<void> {
  const next = frameCallbacks.entries().next().value as [number, FrameCallback] | undefined;
  if (!next) throw new Error("没有待执行的动画帧。");
  frameCallbacks.delete(next[0]);
  await act(async () => next[1](timestamp));
}
