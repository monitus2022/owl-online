import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The first-run gate (#288, #299): a hard name requirement, a browser-local
// name, the request field, and the footer control that reopens the gate. The
// gate is the front page, so the facade, the school name and the promise share
// the screen with the Keeper's name ledger. These tests deliberately start with
// an empty store; the other suites seed a name so they exercise the pages
// behind the gate.
const NAME_KEY = "owl.student.name";
const GATE = "The Keeper of the Records";
const SCHOOL = "Ashcombe Academy of Magic";

test("the gate stops every route until a name is entered", async ({ page }) => {
  for (const path of [
    "/venue/defence-against-the-dark-arts",
    "/cloister",
    "/no-such-room",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: GATE })).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Chat with the professor" }),
    ).toHaveCount(0);
  }

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
  await page.getByRole("button", { name: "Enter the grounds" }).click();
  await expect(page.getByRole("alert")).toHaveText(/ledger needs a name/);

  await page.getByLabel("Your name").fill("12345");
  await page.getByRole("button", { name: "Enter the grounds" }).click();
  await expect(page.getByRole("alert")).toHaveText(/start with a letter/);
  await expect(page.getByRole("heading", { name: GATE })).toBeVisible();
});

test("the gate keeps the school, the ledger and the button above the fold", async ({
  page,
}) => {
  // The phone query and the short-laptop query both matter: the form must not
  // fall below the first screen, and this is the only test that proves it.
  for (const [width, height] of [
    [390, 844],
    [1000, 700],
    [1366, 768],
  ] as const) {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { level: 1, name: SCHOOL }),
    ).toBeVisible();
    await expect(page.getByText(/The revision rooms/)).toBeVisible();
    await expect(page.getByRole("region", { name: GATE })).toBeVisible();
    const box = await page
      .getByRole("button", { name: "Enter the grounds" })
      .boundingBox();
    expect(box, `${width}x${height} button`).not.toBeNull();
    expect(
      box!.y + box!.height,
      `${width}x${height} button bottom`,
    ).toBeLessThanOrEqual(height);
  }
});

test("a name unlocks the academy and survives a reload", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your name").fill("  Ada   Lovelace  ");
  await page.getByRole("button", { name: "Enter the grounds" }).click();

  await expect(page.getByRole("link", { name: "Enter the cloister" })).toBeVisible();
  expect(
    await page.evaluate((key) => window.localStorage.getItem(key), NAME_KEY),
  ).toBe("Ada Lovelace");

  await page.reload();
  await expect(page.getByRole("link", { name: "Enter the cloister" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: GATE }),
  ).toHaveCount(0);
});

test("the name is sent with the chat request", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your name").fill("Ada Lovelace");
  await page.getByRole("button", { name: "Enter the grounds" }).click();
  await expect(page.getByRole("link", { name: "Enter the cloister" })).toBeVisible();

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

test("the footer can change the name and reopens the gate", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your name").fill("Ada Lovelace");
  await page.getByRole("button", { name: "Enter the grounds" }).click();
  await page.getByRole("button", { name: "Change the name" }).click();

  await expect(page.getByRole("heading", { name: GATE })).toBeVisible();
  expect(
    await page.evaluate((key) => window.localStorage.getItem(key), NAME_KEY),
  ).toBeNull();
});

test("axe: the gate has no critical or serious violations", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
});
