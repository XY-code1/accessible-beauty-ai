export const DEFAULT_GUIDE_OPACITY = 0.65;
export const GUIDE_OPACITY_STORAGE_KEY = "accessible-beauty-ai:guide-opacity";

export function parseGuideOpacity(value: string | null) {
  if (value === null || value.trim() === "") return DEFAULT_GUIDE_OPACITY;
  const opacity = Number(value);
  return Number.isFinite(opacity) && opacity >= 0.2 && opacity <= 1
    ? opacity
    : DEFAULT_GUIDE_OPACITY;
}

export function loadGuideOpacity() {
  try {
    return parseGuideOpacity(localStorage.getItem(GUIDE_OPACITY_STORAGE_KEY));
  } catch {
    return DEFAULT_GUIDE_OPACITY;
  }
}

export function saveGuideOpacity(opacity: number) {
  try {
    localStorage.setItem(GUIDE_OPACITY_STORAGE_KEY, String(opacity));
  } catch {
    // Storage can be unavailable in private browsing; the control still works.
  }
}
