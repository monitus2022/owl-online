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
  // The stub publishes a DADA bank only, so Herbology exercises the empty room.
  await page.goto("/venue/herbology");
  await page.getByRole("tab", { name: "Exam room" }).click();
  await expect(page.getByRole("region", { name: "Exam room" })).toBeVisible();
  await page.getByRole("button", { name: "Take a paper" }).click();
  await expect(page.getByText("This department has no papers yet.")).toBeVisible();
});

test("a paper can be sat, marked and found in history", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByRole("tab", { name: "Exam room" }).click();
  await page.getByRole("button", { name: "Take a paper" }).click();

  await expect(
    page.getByText("untimed practice; the student sets the pace"),
  ).toBeVisible();
  const questions = page.locator("fieldset.question");
  await expect(questions).toHaveCount(10);
  for (let index = 0; index < 10; index += 1) {
    const question = questions.nth(index);
    const radios = question.locator('input[type="radio"]');
    if ((await radios.count()) > 0) {
      await radios.first().check();
    } else {
      await question
        .locator("textarea")
        .fill("The lesson turns a feared shape into a comic one.");
    }
  }

  await page.getByRole("button", { name: "Send to the examiners" }).click();
  await expect(
    page.getByRole("heading", { name: "Paper returned" }),
  ).toBeVisible();
  await expect(page.getByText(/\/ 50 marks/)).toBeVisible();
  await expect(page.locator(".mark-row")).toHaveCount(10);
  await expect(
    page.locator(".mark-row-marks").filter({ hasText: /\d+\/8/ }).first(),
  ).toBeVisible();

  await page.getByRole("tab", { name: "Your papers" }).click();
  await expect(page.getByRole("region", { name: "Your papers" })).toBeVisible();
  await expect(page.locator(".history-row")).toHaveCount(1);
  await expect(page.locator(".history-marks")).toHaveText(/\d+\/50/);
});

test("abandoning a paper discards the attempt", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByRole("tab", { name: "Exam room" }).click();
  const started = page.waitForResponse(
    (response) =>
      response.url().includes("/attempts") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Take a paper" }).click();
  const attempt = await (await started).json();
  await expect(page.locator("fieldset.question")).toHaveCount(10);
  const deleted = page.waitForResponse(
    (response) =>
      response.request().method() === "DELETE" &&
      response.url().includes("/v1/attempts/"),
  );
  await page.getByRole("button", { name: "Abandon paper" }).click();
  expect((await deleted).status()).toBe(200);
  await expect(page.getByRole("button", { name: "Take a paper" })).toBeVisible();
  const response = await page.request.get(
    `http://127.0.0.1:8001/v1/attempts/${attempt.attempt_id}`,
  );
  expect(response.status()).toBe(404);
});

test("a blank paper asks before it is sent", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByRole("tab", { name: "Exam room" }).click();
  await page.getByRole("button", { name: "Take a paper" }).click();
  await expect(page.locator("fieldset.question")).toHaveCount(10);
  await expect(page.getByText("0 of 10 answered")).toBeVisible();
  await page.getByRole("button", { name: "Send to the examiners" }).click();
  await expect(
    page.getByText("10 questions left blank. Send the paper anyway?"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Keep working" }).click();
  await expect(
    page.getByRole("button", { name: "Send to the examiners" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Send to the examiners" }).click();
  await expect(
    page.getByText("10 questions left blank. Send the paper anyway?"),
  ).toBeVisible();
  await page
    .locator("fieldset.question")
    .first()
    .locator('input[type="radio"]')
    .first()
    .check();
  await expect(page.getByText("1 of 10 answered")).toBeVisible();
  await expect(
    page.getByText("10 questions left blank. Send the paper anyway?"),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Send to the examiners" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Send to the examiners" }).click();
  await expect(
    page.getByText("9 questions left blank. Send the paper anyway?"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Send anyway" }).click();
  await expect(
    page.getByRole("heading", { name: "Paper returned" }),
  ).toBeVisible();
});

test("clearing the papers empties the history", async ({ page }) => {
  const started = await page.request.post(
    "http://127.0.0.1:8001/v1/exams/dada-1.0.0/attempts",
  );
  const attempt = await started.json();
  await page.request.post(
    `http://127.0.0.1:8001/v1/attempts/${attempt.attempt_id}/grade`,
    { data: { answers: [] } },
  );

  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByRole("tab", { name: "Your papers" }).click();
  await expect(page.locator(".history-row")).toHaveCount(1);
  await page.getByRole("button", { name: "Clear all papers" }).click();
  await expect(
    page.getByText(/Delete every paper in this browser session/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete them" }).click();
  await expect(page.getByText(/The drawer is empty/)).toBeVisible();
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
