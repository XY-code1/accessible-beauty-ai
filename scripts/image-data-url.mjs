// Detect the encoded bytes rather than trusting extensions in imported manifests.
export function imageDataUrl(bytes) {
  const type = bytes
    .subarray(0, 8)
    .equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
    ? "image/png"
    : bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255
      ? "image/jpeg"
      : null;
  if (!type)
    throw new Error("Unsupported image encoding: expected PNG or JPEG");
  return `data:${type};base64,${bytes.toString("base64")}`;
}
