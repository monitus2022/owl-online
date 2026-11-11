import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = [
  ["gate", "/"],
  ["cloister", "/cloister"],
  ["venue", "/venue/defence-against-the-dark-arts"],
] as const;

for (const [name, path] of pages) {
  test(`axe: ${name} has no critical violations`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page }).analyze();
    const critical = results.violations.filter((v) => v.impact === "critical");
    expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
  });
}

test("axe: the exam room has no critical violations", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByRole("tab", { name: "Exam room" }).click();
  await expect(page.getByRole("region", { name: "Exam room" })).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter((v) => v.impact === "critical");
  expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
});

test("axe: the chat after a lesson answer has no critical violations", async ({
  page,
}) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText("A Boggart is a shape-shifter")).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter((v) => v.impact === "critical");
  expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
});
