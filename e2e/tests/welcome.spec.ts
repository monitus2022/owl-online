import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The first-run welcome (#288): a hard name gate, a browser-local name, the
// request field, and the footer control that reopens the welcome. These tests
// deliberately start with an empty store; the other suites seed a name so they
// exercise the pages behind the gate.
const NAME_KEY = "owl.student.name";
const WELCOME = "Welcome to the Academy";

test("the welcome gates every route until a name is entered", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await expect(page.getByRole("heading", { name: WELCOME })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Chat with the professor" }),
  ).toHaveCount(0);

  await page.getByRole("link", { name: "about the Academy", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "About the Academy" }),
  ).toBeVisible();
  await page.goBack();
  await page.getByRole("link", { name: "privacy note" }).click();
  await expect(
    page.getByRole("heading", { name: "Privacy and retention" }),
  ).toBeVisible();
});

test("the name is required and validated", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Enter the Academy" }).click();
  await expect(page.getByRole("alert")).toHaveText(/ledger needs a name/);

  await page.getByLabel("Your name").fill("12345");
  await page.getByRole("button", { name: "Enter the Academy" }).click();
  await expect(page.getByRole("alert")).toHaveText(/start with a letter/);
  await expect(page.getByRole("heading", { name: WELCOME })).toBeVisible();
});

test("a name unlocks the academy and survives a reload", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your name").fill("  Ada   Lovelace  ");
  await page.getByRole("button", { name: "Enter the Academy" }).click();

  await expect(page.getByRole("link", { name: "Enter the grounds" })).toBeVisible();
  expect(
    await page.evaluate((key) => window.localStorage.getItem(key), NAME_KEY),
  ).toBe("Ada Lovelace");

  await page.reload();
  await expect(page.getByRole("link", { name: "Enter the grounds" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: WELCOME }),
  ).toHaveCount(0);
});

test("the name is sent with the chat request", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your name").fill("Ada Lovelace");
  await page.getByRole("button", { name: "Enter the Academy" }).click();
  await expect(page.getByRole("link", { name: "Enter the grounds" })).toBeVisible();

  let posted: Record<string, unknown> | null = null;
  await page.route("**/v1/chat/stream", async (route) => {
    posted = route.request().postDataJSON() as Record<string, unknown>;
    await route.continue();
  });

  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText("A Boggart is a shape-shifter")).toBeVisible();
  expect(posted).not.toBeNull();
  expect(posted?.student_name).toBe("Ada Lovelace");
});

test("the footer can change the name and reopens the welcome", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your name").fill("Ada Lovelace");
  await page.getByRole("button", { name: "Enter the Academy" }).click();
  await page.getByRole("button", { name: "Change the name" }).click();

  await expect(page.getByRole("heading", { name: WELCOME })).toBeVisible();
  expect(
    await page.evaluate((key) => window.localStorage.getItem(key), NAME_KEY),
  ).toBeNull();
});

test("axe: the welcome has no critical violations", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page }).analyze();
  const critical = results.violations.filter((v) => v.impact === "critical");
  expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
});
