import { expect, test } from "@playwright/test";
import { begin, installCamera } from "./harness";

test("mobile practice keeps the eye, instruction and primary action together", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installCamera(page);
  await begin(page);
  await expect(
    page.getByRole("heading", { name: "先画一小段眼尾" }),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "眼部已定位" }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "查看整体画面", exact: true }),
  ).toBeVisible();
  for (const item of [
    page.getByLabel("眼部放大画面"),
    page.getByRole("heading", { name: "先画一小段眼尾" }),
    page.getByRole("button", { name: "检查这一步" }),
  ]) {
    const box = await item.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height).toBeLessThanOrEqual(844);
  }
  await page.screenshot({
    path: "test-results/v3-practice-390.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "查看整体画面", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "回到眼部放大", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "回到眼部放大", exact: true }).click();
  await expect(page.getByRole("button", { name: "检查这一步" })).toBeEnabled();
});

test("mobile startup exposes model failure and restores retry without enabling fake guidance", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installCamera(page, { modelFailure: true });
  await page.goto("/#/eyeliner");
  await page.getByRole("button", { name: "开启摄像头", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("眼部模型加载失败");
  await expect(
    page.getByRole("button", { name: "重新开启摄像头" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "仅跟随指引练习" }),
  ).toBeDisabled();
  await expect
    .poll(() =>
      page.evaluate(() =>
        (
          window as unknown as { __cameraTest: { streams: MediaStream[] } }
        ).__cameraTest.streams.every((stream) =>
          stream.getTracks().every((track) => track.readyState === "ended"),
        ),
      ),
    )
    .toBe(true);
});

test("display preferences keep the captured baseline and practice step", async ({
  page,
}) => {
  await installCamera(page);
  await begin(page);
  await page.getByRole("button", { name: "看效果", exact: true }).click();
  await page.getByRole("button", { name: "跟着画", exact: true }).click();
  await page.getByText("显示设置", { exact: true }).click();
  await page.getByLabel("高对比度参考线").check();
  await page.getByLabel("引导线透明度").fill("50");
  await expect(
    page.getByRole("heading", { name: "先画一小段眼尾" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "检查这一步" })).toBeEnabled();
  await expect(page.getByLabel("眼部放大画面")).toHaveAttribute(
    "data-opacity",
    "0.5",
  );
  await expect(page.getByLabel("眼部放大画面")).toHaveAttribute(
    "data-step",
    "wing",
  );
});

test("guide opacity defaults safely and exposes percentage semantics", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("accessible-beauty-ai:guide-opacity", "broken"),
  );
  await page.goto("/#/eyeliner");
  await page.getByText("显示设置", { exact: true }).click();
  const slider = page.getByLabel("引导线透明度");
  await expect(slider).toHaveValue("65");
  await expect(slider).toHaveAttribute("aria-valuemin", "20");
  await expect(slider).toHaveAttribute("aria-valuemax", "100");
  await expect(slider).toHaveAttribute("aria-valuenow", "65");
  await expect(page.locator("output")).toHaveText("65%");
  await slider.press("ArrowRight");
  await expect(slider).toHaveAttribute("aria-valuenow", "75");
});

test("guide opacity updates immediately, persists, and does not restart vision", async ({
  page,
}) => {
  await installCamera(page);
  await begin(page);
  await page.getByText("显示设置", { exact: true }).click();
  const slider = page.getByLabel("引导线透明度");
  const before = await page.evaluate(() => {
    const state = (
      window as unknown as {
        __cameraTest: { streams: MediaStream[]; detectors: number };
      }
    ).__cameraTest;
    return { streams: state.streams.length, detectors: state.detectors };
  });

  await slider.fill("20");
  await expect(slider).toHaveAttribute("aria-valuenow", "20");
  await expect(page.locator('canvas[data-opacity="0.2"]')).toHaveCount(2);
  await slider.fill("100");
  await expect(slider).toHaveAttribute("aria-valuenow", "100");
  await expect(page.locator('canvas[data-opacity="1"]')).toHaveCount(2);
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await slider.fill("40");
  await expect(page.locator('canvas[data-opacity="0.4"]')).toHaveCount(2);
  await page.getByRole("button", { name: "继续练习", exact: true }).click();
  await slider.fill("70");
  await page.getByRole("button", { name: "恢复默认" }).click();
  await expect(slider).toHaveValue("65");
  await slider.fill("80");

  expect(
    await page.evaluate(() => {
      const state = (
        window as unknown as {
          __cameraTest: { streams: MediaStream[]; detectors: number };
        }
      ).__cameraTest;
      return { streams: state.streams.length, detectors: state.detectors };
    }),
  ).toEqual(before);

  await page.reload();
  await page.getByText("显示设置", { exact: true }).click();
  await expect(page.getByLabel("引导线透明度")).toHaveValue("80");
});

test("320px, 200% zoom approximation and reduced motion keep core controls usable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await installCamera(page);
  await page.goto("/#/eyeliner");
  await expect(
    page.getByRole("button", { name: "开启摄像头", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const box = await page
    .getByRole("button", { name: "开启摄像头", exact: true })
    .boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThanOrEqual(44);
  expect(box!.height).toBeGreaterThanOrEqual(44);
  await page.addStyleTag({ content: "body { zoom: 2 }" });
  await expect(
    page.getByRole("button", { name: "开启摄像头", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "开启摄像头", exact: true })
    .scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(
      () =>
        getComputedStyle(document.querySelector(".eye-art")!).animationDuration,
    ),
  ).toMatch(/^(0\.01ms|1e-05s)$/);
});
