import { useEffect, useRef, useState, type RefObject } from "react";
import { eyeCrop } from "../guidance/geometry";
import { lightingMessage } from "../vision/lighting";
import type { VisionOutput } from "../types";

export const LIGHTING_SAMPLE_MS = 500;
export const LIGHTING_SHOW_SAMPLES = 4;
export const LIGHTING_CLEAR_SAMPLES = 3;

// Advisory only: these conservative pixel thresholds never gate capture or analysis.
export function useLightingHint(
  video: RefObject<HTMLVideoElement | null>,
  vision: VisionOutput | null,
  enabled: boolean,
  revision: number,
) {
  const latest = useRef(vision);
  useEffect(() => {
    latest.current = vision;
  }, [vision]);
  const [hint, setHint] = useState("");
  const detected = !!vision?.eye;
  useEffect(() => {
    setHint("");
    if (!enabled || !detected) return;
    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 24;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;
    let candidate = "",
      repeats = 0,
      lastFrame = -1;
    const timer = setInterval(() => {
      const frame = latest.current,
        source = video.current;
      if (
        !frame?.eye ||
        !source ||
        source.readyState < 2 ||
        performance.now() - frame.timestamp > 700
      ) {
        candidate = "";
        repeats = 0;
        setHint("");
        return;
      }
      if (source.currentTime === lastFrame) return;
      lastFrame = source.currentTime;
      try {
        const crop = eyeCrop(frame.eye, { x: frame.width, y: frame.height });
        ctx.drawImage(
          source,
          crop.x,
          crop.y,
          crop.width,
          crop.height,
          0,
          0,
          32,
          24,
        );
        const data = ctx.getImageData(0, 0, 32, 24).data;
        const next = lightingMessage(data);
        repeats = next === candidate ? repeats + 1 : 1;
        candidate = next;
        if (
          repeats >=
          (next ? LIGHTING_SHOW_SAMPLES : LIGHTING_CLEAR_SAMPLES)
        )
          setHint(next);
      } catch {
        candidate = "";
        repeats = 0;
        setHint("");
      }
    }, LIGHTING_SAMPLE_MS);
    return () => clearInterval(timer);
  }, [video, enabled, detected, revision]);
  return enabled && detected ? hint : "";
}
