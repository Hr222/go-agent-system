import { useCallback, useEffect, useRef, useState } from "react";

type RenderDelta = (delta: string) => void;

const DISPLAY_INTERVAL_MS = 30;
const TARGET_DRAIN_FRAMES = 32;

export function useDeltaRenderQueue() {
  const [isRendering, setIsRendering] = useState(false);
  const queueRef = useRef<string[]>([]);
  const frameRef = useRef<number | null>(null);
  const renderDeltaRef = useRef<RenderDelta | null>(null);
  const settledRef = useRef<(() => void) | null>(null);
  const flushRef = useRef<(timestamp: number) => void>(() => undefined);
  const lastDisplayAtRef = useRef<number | null>(null);
  const batchSizeRef = useRef(1);

  const cancelScheduledFrame = useCallback(() => {
    if (frameRef.current === null) return;
    cancelFrame(frameRef.current);
    frameRef.current = null;
  }, []);

  const scheduleFlush = useCallback(() => {
    if (frameRef.current !== null) return;
    frameRef.current = requestFrame((timestamp) => {
      frameRef.current = null;
      flushRef.current(timestamp);
    });
  }, []);

  flushRef.current = (timestamp) => {
    if (shouldWaitForNextDisplay(lastDisplayAtRef.current, timestamp)) {
      scheduleFlush();
      return;
    }

    const unitCount = Math.min(batchSizeRef.current, queueRef.current.length);
    const delta = queueRef.current.splice(0, unitCount).join("");
    if (delta) {
      renderDeltaRef.current?.(delta);
      lastDisplayAtRef.current = timestamp;
    }

    if (queueRef.current.length > 0) {
      scheduleFlush();
      return;
    }
    batchSizeRef.current = 1;

    const onSettled = settledRef.current;
    if (!onSettled) {
      setIsRendering(false);
      return;
    }
    settledRef.current = null;
    frameRef.current = requestFrame(() => {
      frameRef.current = null;
      setIsRendering(false);
      onSettled();
    });
  };

  const start = useCallback((renderDelta: RenderDelta) => {
    cancelScheduledFrame();
    queueRef.current = [];
    renderDeltaRef.current = renderDelta;
    settledRef.current = null;
    lastDisplayAtRef.current = null;
    batchSizeRef.current = 1;
    setIsRendering(false);
  }, [cancelScheduledFrame]);

  const enqueue = useCallback((delta: string) => {
    if (!delta) return;
    queueRef.current.push(...splitIntoDisplayUnits(delta));
    batchSizeRef.current = Math.max(
      batchSizeRef.current,
      unitsForNextDisplay(queueRef.current.length),
    );
    setIsRendering(true);
    scheduleFlush();
  }, [scheduleFlush]);

  const settle = useCallback((onSettled: () => void) => {
    settledRef.current = onSettled;
    setIsRendering(true);
    if (frameRef.current === null) scheduleFlush();
  }, [scheduleFlush]);

  useEffect(() => () => cancelScheduledFrame(), [cancelScheduledFrame]);

  return { enqueue, isRendering, settle, start };
}

function shouldWaitForNextDisplay(lastDisplayAt: number | null, timestamp: number): boolean {
  return lastDisplayAt !== null && timestamp - lastDisplayAt < DISPLAY_INTERVAL_MS;
}

function unitsForNextDisplay(pendingUnitCount: number): number {
  return Math.max(1, Math.ceil(pendingUnitCount / TARGET_DRAIN_FRAMES));
}

function splitIntoDisplayUnits(text: string): string[] {
  const Segmenter = (Intl as unknown as {
    Segmenter?: new () => { segment: (source: string) => Iterable<{ segment: string }> };
  }).Segmenter;
  if (!Segmenter) return Array.from(text);
  return Array.from(new Segmenter().segment(text), (entry) => entry.segment);
}

function requestFrame(callback: FrameRequestCallback): number {
  if (typeof window !== "undefined" && window.requestAnimationFrame) {
    return window.requestAnimationFrame(callback);
  }
  return globalThis.setTimeout(() => callback(performance.now()), 16) as unknown as number;
}

function cancelFrame(frame: number): void {
  if (typeof window !== "undefined" && window.cancelAnimationFrame) {
    window.cancelAnimationFrame(frame);
    return;
  }
  globalThis.clearTimeout(frame);
}
