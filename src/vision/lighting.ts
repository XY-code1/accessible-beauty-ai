// Conservative advisory thresholds, not exposure measurements or acceptance gates.
// Caller supplies a 32×24 raw eye crop; shared with the offline validation runner.
export function lightingMessage(data: Uint8ClampedArray): string {
  if (!data.length || data.length % 4) return "";
  let sum = 0,
    highlights = 0;
  const count = data.length / 4;
  for (let i = 0; i < data.length; i += 4) {
    const value = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    sum += value;
    if (value >= 245) highlights++;
  }
  return sum / count < 35
    ? "眼部画面偏暗，可尝试增加均匀的正面光线。"
    : highlights / count > 0.3
      ? "眼部高亮区域较多，可尝试调整位置、避开直射光。"
      : "";
}
