import { expect, test } from "@playwright/test";
import { installCamera, setCamera, waitForCameraReady } from "./harness";

test("dark-eye advice does not prevent guidance and clears on pause or lost face", async ({
  page,
}) => {
  await installCamera(page);
  await page.goto("/#/eyeliner");
  await page.getByRole("button", { name: "开启摄像头", exact: true }).click();
  await waitForCameraReady(page);
  await setCamera(page, { mark: "dark" });
  await expect(
    page.getByText("眼部画面偏暗，可尝试增加均匀的正面光线。", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "仅跟随指引练习", exact: true })
    .click();
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await expect(
    page.getByText("眼部画面偏暗，可尝试增加均匀的正面光线。", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "继续练习", exact: true }).click();
  await expect(
    page.getByText("眼部画面偏暗，可尝试增加均匀的正面光线。", { exact: true }),
  ).toBeVisible();
  await setCamera(page, { face: false });
  await expect(
    page.getByText("眼部画面偏暗，可尝试增加均匀的正面光线。", { exact: true }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() =>
      (window as unknown as { __cameraTest: { streams: MediaStream[] } })
        .__cameraTest.streams.at(-1)?.getVideoTracks()[0]?.readyState,
    ),
  ).toBe("live");
  await expect(page.locator(".view-hint")).toContainText(
    "眼部暂时被遮挡或移出画面",
  );
});

test("highlights clear after normal frames and target changes reset advice", async ({
  page,
}) => {
  await installCamera(page);
  await page.goto("/#/eyeliner");
  await page.getByRole("button", { name: "开启摄像头", exact: true }).click();
  await waitForCameraReady(page);
  const hint = page.getByText(
    "眼部高亮区域较多，可尝试调整位置、避开直射光。",
    { exact: true },
  );
  await setCamera(page, { mark: "bright" });
  await expect(hint).toBeVisible();
  await page.getByRole("button", { name: "左眼", exact: true }).click();
  await expect(hint).toHaveCount(0);
  await expect(hint).toBeVisible();
  await setCamera(page, { mark: "none" });
  await expect(hint).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "确认形状，拍画前照片" }),
  ).toBeEnabled();
});

test("a transient lighting change stays quiet and capture cancellation resets advice", async ({
  page,
}) => {
  await installCamera(page);
  await page.goto("/#/eyeliner");
  await page.getByRole("button", { name: "开启摄像头", exact: true }).click();
  await waitForCameraReady(page);
  const hint = page.locator(".lighting-hint");
  await setCamera(page, { mark: "dark" });
  // Less than three 500ms observations must not produce an announcement.
  await page.waitForTimeout(400);
  await setCamera(page, { mark: "none" });
  await expect(hint).toHaveCount(0);
  await page.waitForTimeout(1600);
  await expect(hint).toHaveCount(0);
  await setCamera(page, { mark: "dark" });
  await expect(hint).toBeVisible();
  await page.getByRole("button", { name: "确认形状，拍画前照片" }).click();
  await expect(hint).toHaveCount(0);
  await page.getByRole("button", { name: "取消，返回练习" }).click();
  await expect(hint).toHaveCount(0);
  await expect(hint).toBeVisible();
});
