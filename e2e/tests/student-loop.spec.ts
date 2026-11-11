import { expect, test } from "@playwright/test";

const DADA = "Defence Against the Dark Arts";

test("gate -> cloister -> DADA venue", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Enter the grounds" }).click();
  await expect(page.getByRole("heading", { name: "The Cloister" })).toBeVisible();
  await page.getByRole("link", { name: new RegExp(DADA) }).click();
  await expect(
    page.getByRole("region", { name: "Chat with the professor" }),
  ).toBeVisible();
});

test("a lesson question returns prose and citations", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await expect(
    page.getByRole("region", { name: "Chat with the professor" }),
  ).toBeVisible();
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText("A Boggart is a shape-shifter")).toBeVisible();
  await expect(page.getByText("Lesson notes")).toBeVisible();
  await expect(
    page.getByText("dada-test-material", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("lesson:b1-c01-0000#b1-c01-0000", { exact: true }),
  ).toBeVisible();
});

test("a pronoun follow-up resolves across turns", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("Who is Professor Lupin?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(
    page.getByText("Professor Lupin taught Defence Against the Dark Arts"),
  ).toBeVisible();
  await page.getByLabel("Your question").fill("who trained him?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(
    page.getByText("Remus Lupin trained Professor Lupin"),
  ).toBeVisible();
});

test("the identity answer is scripted", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("Who are you?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText("Professor Crane")).toBeVisible();
});

test("an off-topic question abstains in world", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is the capital of France?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/confirm/)).toBeVisible();
});

test("the exam room renders the no-papers state", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByRole("tab", { name: "Exam room" }).click();
  await expect(page.getByRole("region", { name: "Exam room" })).toBeVisible();
  await page.getByRole("button", { name: "Take a paper" }).click();
  await expect(page.getByText("This department has no papers yet.")).toBeVisible();
});

test("the venue stays open when the subjects API is unreachable", async ({
  page,
}) => {
  await page.route("**/v1/subjects", (route) => route.abort());
  await page.goto("/venue/defence-against-the-dark-arts");
  await expect(
    page.getByRole("region", { name: "Chat with the professor" }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText(
    "reviewed notes are not loaded",
  );
});

test("the education paraphrase answers from the persona fact", async ({
  page,
}) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("did you study in hogwarts?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText("I studied at Hogwarts")).toBeVisible();
  await expect(page.getByText("persona:professor.education")).toBeVisible();
});

test("a meta question about the exam is refused", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("Can I ask a question about exam?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/examination/)).toBeVisible();
});
