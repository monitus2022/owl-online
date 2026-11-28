import { expect, test } from "@playwright/test";

const DADA = "Defence Against the Dark Arts";
const API_BASE = "http://127.0.0.1:8001";

// The gate (#288) stops every route until a name is entered. Seed one so these tests
// start behind the gate; welcome.spec.ts covers the gate itself.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("owl.student.name", "Test Student");
  });
});

test("gate -> cloister -> DADA venue", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Enter the cloister" }).click();
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
  // Wait for the live lesson flag, then pin the mode on the request so a slow
  // /v1/subjects cannot silently turn this into an auto-routed answer.
  await expect(
    page.getByText(/I teach from the department's reviewed notes/),
  ).toBeVisible();
  const stream = page.waitForRequest("**/v1/chat/stream");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  const request = await stream;
  expect(request.postDataJSON()).toMatchObject({ mode: "lesson" });
  const answer = page
    .locator(".chat-text")
    .filter({ hasText: "A Boggart is a shape-shifter" });
  await expect(answer).toBeVisible();
  await expect(
    page.getByText("Composed from the department notes"),
  ).toBeVisible();
  await expect(answer).toHaveText(
    "A Boggart is a shape-shifter that takes the shape of what the watcher fears most.",
  );
  await expect(answer).not.toContainText("[mat:");
  await expect(answer).not.toContainText("[b1-c01-0000]");
  await expect(page.getByText("Sources", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Test · Material" }),
  ).toBeVisible();
  await expect(
    page.getByText("Book 1, Chapter 1", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Test · Material" }).click();
  const note = page.getByRole("region", { name: /^Reviewed note/ });
  await expect(note).toBeVisible();
  await expect(note.getByText("Boggart", { exact: true })).toBeVisible();
  await expect(
    note.getByText(
      "A Boggart takes the shape of what the watcher fears most. The counter is the Banishing Charm, and the ward keeps a separate note [b2-c03-0007].",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(note).not.toContainText("[b1-c01-0000]");
  await expect(note).toContainText("[b2-c03-0007]");
  await expect(note.getByText(/Book 1, Chapter 1/)).toBeVisible();
  await expect(note.getByText("b1-c01-0000", { exact: true })).toBeVisible();
  await page.getByText("Source details").click();
  const details = page.locator(".citation-details");
  await expect(
    details.getByText("dada-test-material", { exact: true }),
  ).toBeVisible();
  await expect(
    details.getByText("lesson:b1-c01-0000#b1-c01-0000", { exact: true }),
  ).toBeVisible();
});

test("a failed reviewed note says so and offers a retry", async ({ page }) => {
  await page.route("**/v1/materials/**", (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: "{}",
    }),
  );
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await page.getByRole("button", { name: "Test · Material" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "The reviewed note could not be opened.",
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("the dev evidence inspector shows the retrieved evidence", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText("A Boggart is a shape-shifter")).toBeVisible();

  const inspector = page.locator(".evidence-inspector");
  await expect(inspector).toBeVisible();
  await inspector.getByText(/Evidence inspector/).click();
  await expect(inspector).toContainText("prompt");
  await expect(inspector).toContainText("attempts");
  await expect(inspector).toContainText("grounded");
  await expect(inspector).toContainText(/[0-9a-f]{16}/);
  await expect(inspector).toContainText("dada-test-material");
});


test("the reviewed note fits a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await page.getByRole("button", { name: "Test · Material" }).click();
  await expect(
    page.getByRole("region", { name: /^Reviewed note/ }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
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
  await expect(
    page.getByText("The expected answer:", { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByText("The professor's note:").first()).toBeVisible();
  await expect(page.getByText("Facts and accuracy").first()).toBeVisible();
  await expect(page.getByText("Model:", { exact: false })).toHaveCount(0);
  await expect(page.getByText(/b1-c01-0000/)).toHaveCount(0);

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
    page.getByText(/Delete every paper from this visit/),
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

test("the room opens when the subjects request is slow", async ({ page }) => {
  await page.route("**/v1/subjects", () => {
    // Leave the request pending: the room must open on the static data
    // instead of waiting for a response that may never arrive.
  });
  await page.goto("/venue/defence-against-the-dark-arts");
  await expect(page.getByLabel("Your question")).toBeEnabled({
    timeout: 4000,
  });
});

test("a failed answer offers a retry", async ({ page }) => {
  let attempts = 0;
  await page.route("**/v1/chat/stream", async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.continue();
      return;
    }
    attempts += 1;
    if (attempts === 1) {
      await route.abort();
      return;
    }
    await route.continue();
  });
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(
    page.getByText("Could not reach the Academy. Is the server running?"),
  ).toBeVisible();
  await page.getByRole("button", { name: /Try again/ }).click();
  await expect(page.getByText("A Boggart is a shape-shifter")).toBeVisible();
  // The retry reuses the failed turn; the question is not sent twice.
  await expect(page.locator(".chat-student")).toHaveCount(1);
});

test("a stream that closes without a final offers a retry", async ({ page }) => {
  await page.route("**/v1/chat/stream", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers: {
        "Access-Control-Allow-Origin": "http://127.0.0.1:5500",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      },
      // A keep-alive comment is not a final event, and the stream then closes.
      body: ": ping - 2026-11-26T00:00:00Z\n\n",
    }),
  );
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/closed the answer early/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Try again/ })).toBeVisible();
});

test("a ping-only stream times out and offers a retry", async ({ page }) => {
  await page.clock.install();
  await page.route("**/v1/chat/stream", (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    return route.continue({ url: `${API_BASE}/v1/test/ping-stream` });
  });
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  const stream = page.waitForResponse("**/v1/test/ping-stream");
  await page.getByRole("button", { name: "Ask" }).click();
  await stream;
  // Let real pings arrive while the fake clock advances. A timer reset on
  // every raw read would move its deadline past 36 s; the data-event timer
  // stays at 30 s from the last real event.
  for (let i = 0; i < 6; i += 1) {
    await page.clock.runFor(1000);
    await page.waitForTimeout(150);
  }
  await page.clock.fastForward(25_100);
  await expect(page.getByText(/The answer stalled/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Try again/ })).toBeVisible();
});

test("a stalled error body times out instead of hanging", async ({ page }) => {
  await page.clock.install();
  await page.route("**/v1/chat/stream", (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    return route.continue({ url: `${API_BASE}/v1/test/stall-error` });
  });
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  const response = page.waitForResponse("**/v1/test/stall-error");
  await page.getByRole("button", { name: "Ask" }).click();
  await response;
  await page.clock.fastForward(21_000);
  await expect(page.getByText(/did not answer in time/)).toBeVisible();
});

test("a chat request that never returns headers times out", async ({ page }) => {
  await page.clock.install();
  await page.route("**/v1/chat/stream", (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    // Leave the POST pending: no headers, no stream.
  });
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("What is a Boggart?");
  const post = page.waitForRequest(
    (request) =>
      request.method() === "POST" && request.url().includes("/v1/chat/stream"),
  );
  await page.getByRole("button", { name: "Ask" }).click();
  await post;
  await page.clock.fastForward(21_000);
  await expect(page.getByText(/did not answer in time/)).toBeVisible();
});

test("a cached subjects payload opens the next venue while the API hangs", async ({
  page,
}) => {
  const first = page.waitForResponse("**/v1/subjects");
  await page.goto("/venue/defence-against-the-dark-arts");
  await first;
  await page.waitForFunction(
    () => sessionStorage.getItem("owl.subjects.v1") !== null,
  );
  await page.route("**/v1/subjects", () => {
    // Hang the refresh so only the session cache can open the next room.
  });
  await page.goto("/venue/charms");
  await expect(page.getByLabel("Your question")).toBeEnabled({
    timeout: 1500,
  });
});

test("a subjects request that never answers times out and shows the note", async ({
  page,
}) => {
  await page.clock.install();
  await page.route("**/v1/subjects", () => {
    // Never answer: the 5 s abort must fall back to the static data.
  });
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.clock.fastForward(2_100);
  await expect(page.getByLabel("Your question")).toBeEnabled();
  await page.clock.fastForward(4_500);
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
  await expect(
    page.getByText("Professor's note", { exact: true }),
  ).toBeVisible();
  await page.getByText("Source details").click();
  await expect(
    page.getByText("persona:professor.education", { exact: true }),
  ).toBeVisible();
});

test("a meta question about the exam is refused", async ({ page }) => {
  await page.goto("/venue/defence-against-the-dark-arts");
  await page.getByLabel("Your question").fill("Can I ask a question about exam?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/examination/)).toBeVisible();
});
