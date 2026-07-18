import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const frontendDir = path.resolve(path.dirname(__filename), "..");
const repoRoot = path.resolve(frontendDir, "..");
const reportDir = path.join(repoRoot, "docs", "reports", "e2e");
const screenshotDir = path.join(reportDir, "screenshots");
const reportPath = path.join(reportDir, "wishub-mvp-e2e-report.md");
const frontendUrl = "http://127.0.0.1:15173";
const backendUrl = "http://127.0.0.1:18000";
const runId = timestamp();
const backendTmpPrefix = `/tmp/wishub_e2e_report_${runId}`;

const cases = [];
const processes = [];

async function main() {
  await mkdir(screenshotDir, { recursive: true });
  await cleanupTemp();

  processes.push(
    startProcess(
      "backend",
      "uv",
      ["run", "--package", "backend", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "18000"],
      repoRoot,
      {
        WISHUB_SQLITE_PATH: `${backendTmpPrefix}.sqlite3`,
        WISHUB_UPLOAD_DIR: `${backendTmpPrefix}_uploads`,
        WISHUB_CHROMA_PATH: `${backendTmpPrefix}_chroma`,
        ANONYMIZED_TELEMETRY: "False",
      },
    ),
  );
  await waitFor(`${backendUrl}/api/v1/knowledge-base/summary`, 180_000);

  processes.push(
    startProcess("frontend", "npx", ["vite", "--host", "127.0.0.1", "--port", "15173"], frontendDir, {
      VITE_API_BASE_URL: backendUrl,
    }),
  );
  await waitFor(frontendUrl, 60_000);

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });

  try {
    await executeCases(page);
  } finally {
    await browser.close();
    await stopProcesses();
    await cleanupTemp();
  }

  await writeReport();
  printSummary();
}

async function executeCases(page) {
  await page.goto(frontendUrl);

  await runCase(page, {
    id: "E2E-001",
    name: "知识库空态加载",
    expected: "首次进入知识库页面时，目录数为 0，并展示空态上传引导。",
    action: async () => {
      await expectVisible(page.getByRole("heading", { name: "知识库" }));
      await expectVisible(page.getByText("当前暂无知识库文档"));
      await expectText(page.locator(".stat-card strong"), "0");
    },
  });

  await runCase(page, {
    id: "E2E-002",
    name: "非 Markdown 文件本地拦截",
    expected: "选择非 .md 文件后展示格式错误提示，上传按钮保持禁用。",
    action: async () => {
      const invalidFile = path.join("/tmp", `wishub-invalid-${runId}.txt`);
      await writeFile(invalidFile, "not markdown");
      await page.locator('input[type="file"]').setInputFiles(invalidFile);
      await expectVisible(page.getByText("仅支持 Markdown 文件（.md）"));
      await expectDisabled(page.getByRole("button", { name: "上传并入库" }));
    },
  });

  await runCase(page, {
    id: "E2E-003",
    name: "Markdown 上传并刷新有效目录",
    expected: "上传合法 Markdown 后，文档处理为 READY，目录数刷新为 1，列表展示可问答文档。",
    action: async () => {
      const markdownFile = path.join("/tmp", `wishub-fixture-${runId}.md`);
      await writeFile(markdownFile, fixtureMarkdown());
      await page.locator('input[type="file"]').setInputFiles(markdownFile);
      await expectVisible(page.getByText(/wishub-fixture-.*\.md/).first());
      await page.getByRole("button", { name: "上传并入库" }).click();
      await expectVisible(page.getByText(/已加入知识库/), 30_000);
      await expectText(page.locator(".stat-card strong"), "1");
      await expectVisible(page.getByText(path.basename(markdownFile)).first());
      await expectVisible(page.getByText("可问答").first());
    },
  });

  await page.getByRole("button", { name: "知识问答" }).click();
  await expectVisible(page.getByRole("heading", { name: "知识问答" }));
  const questionBox = page.getByPlaceholder("输入一个关于知识库的问题…");

  await runCase(page, {
    id: "E2E-004",
    name: "知识库内问题返回回答与引用",
    expected: "对知识库内问题返回 answer，展示引用依据和 externalKnowledgeUsed=false。",
    action: async () => {
      await questionBox.fill("知识库上传支持什么格式？");
      await page.getByRole("button", { name: "提交问题" }).click();
      await expectVisible(page.getByText("基于知识库的回答"));
      await expectVisible(page.getByRole("heading", { name: "引用依据" }));
      await expectVisible(page.getByText("外部知识：否"));
      await expectVisible(page.getByText(/wishub-fixture-.*\.md/).first());
    },
  });

  await runCase(page, {
    id: "E2E-005",
    name: "知识库外问题明确拒答",
    expected: "对知识库无依据问题返回 refusal，不展示知识库外结论。",
    action: async () => {
      await questionBox.fill("明天北京天气怎么样？");
      await page.getByRole("button", { name: "提交问题" }).click();
      await expectVisible(page.getByText("当前知识库暂无相关依据"));
    },
  });

  await runCase(page, {
    id: "E2E-006",
    name: "模糊问题返回澄清提示",
    expected: "对缺少具体对象或条件的问题返回 clarification，要求补充问题信息。",
    action: async () => {
      await questionBox.fill("怎么做");
      await page.getByRole("button", { name: "提交问题" }).click();
      await expectVisible(page.getByText("请补充问题信息"));
    },
  });

  await runCase(page, {
    id: "E2E-007",
    name: "页面查看大模型调用日志",
    expected: "完成一次需要大模型生成的问答后，可在调用日志页面查看请求大模型和大模型原始响应数据。",
    action: async () => {
      await page.getByRole("button", { name: "调用日志" }).click();
      await expectVisible(page.getByRole("heading", { name: "调用日志" }));
      await expectVisible(page.getByRole("heading", { name: "大模型请求与响应日志" }));
      await expectVisible(page.locator(".log-card-header strong").filter({ hasText: "知识库上传支持什么格式？" }));
      await expectVisible(page.getByText("请求大模型"));
      await expectVisible(page.getByText("大模型原始响应"));
    },
  });
}

async function runCase(page, definition) {
  const start = performance.now();
  let status = "PASS";
  let error = "";

  try {
    await definition.action();
  } catch (caseError) {
    status = "FAIL";
    error = caseError instanceof Error ? caseError.message : String(caseError);
  }

  const durationMs = Math.round(performance.now() - start);
  const screenshotName = `${runId}-${definition.id}.png`;
  const screenshotPath = path.join(screenshotDir, screenshotName);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  cases.push({
    ...definition,
    status,
    durationMs,
    screenshotName,
    screenshotPath,
    error,
  });

  if (status === "FAIL") {
    throw new Error(`${definition.id} ${definition.name} failed: ${error}`);
  }
}

async function writeReport() {
  const totalDurationMs = cases.reduce((sum, item) => sum + item.durationMs, 0);
  const passed = cases.filter((item) => item.status === "PASS").length;
  const failed = cases.length - passed;
  const now = new Date().toLocaleString("zh-CN", { hour12: false });

  const lines = [
    "# wishub MVP E2E 测试报告",
    "",
    `- 测试时间：${now}`,
    "- 测试工具：Playwright Chromium",
    `- 前端地址：${frontendUrl}`,
    `- 后端地址：${backendUrl}`,
    "- 后端数据：临时 SQLite + 临时 Chroma + 临时上传目录",
    `- 总用例数：${cases.length}`,
    `- 通过：${passed}`,
    `- 失败：${failed}`,
    `- 用例总耗时：${formatDuration(totalDurationMs)}`,
    "",
    "## 用例明细",
    "",
    "| 用例 ID | 用例名称 | 结果 | 耗时 | 截图 |",
    "|---|---|---:|---:|---|",
    ...cases.map(
      (item) =>
        `| ${item.id} | ${item.name} | ${item.status} | ${formatDuration(item.durationMs)} | [截图](./screenshots/${item.screenshotName}) |`,
    ),
    "",
    "## 逐用例说明",
    "",
  ];

  for (const item of cases) {
    lines.push(`### ${item.id} ${item.name}`);
    lines.push("");
    lines.push(`- 结果：${item.status}`);
    lines.push(`- 执行耗时：${formatDuration(item.durationMs)}`);
    lines.push(`- 验收标准：${item.expected}`);
    if (item.error) {
      lines.push(`- 失败原因：${item.error.replaceAll("\n", " ")}`);
    }
    lines.push(`- 截图：[${item.screenshotName}](./screenshots/${item.screenshotName})`);
    lines.push("");
    lines.push(`![${item.id} ${item.name}](./screenshots/${item.screenshotName})`);
    lines.push("");
  }

  lines.push("## QA 结论");
  lines.push("");
  if (failed === 0) {
    lines.push("本轮 Playwright E2E 测试全部通过。MVP 主链路和核心边界状态符合当前验收预期。");
  } else {
    lines.push("本轮 Playwright E2E 测试存在失败用例，需修复后重新执行。");
  }
  lines.push("");

  await writeFile(reportPath, `${lines.join("\n")}\n`, "utf-8");
}

function printSummary() {
  console.log(`E2E report generated: ${reportPath}`);
  for (const item of cases) {
    console.log(`${item.status} ${item.id} ${item.name} ${formatDuration(item.durationMs)}`);
  }
}

function startProcess(name, command, args, cwd, extraEnv = {}) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...extraEnv },
    stdio: ["ignore", "pipe", "pipe"],
  });

  child.stdout.on("data", (data) => process.stdout.write(`[${name}] ${data}`));
  child.stderr.on("data", (data) => process.stderr.write(`[${name}] ${data}`));
  child.on("exit", (code, signal) => {
    if (code !== 0 && signal !== "SIGTERM" && signal !== "SIGINT") {
      console.error(`[${name}] exited with code ${code ?? signal}`);
    }
  });
  return child;
}

async function stopProcesses() {
  for (const child of processes.reverse()) {
    if (!child.killed) {
      child.kill("SIGTERM");
    }
  }
}

async function waitFor(url, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // keep waiting
    }
    await delay(500);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function expectVisible(locator, timeout = 15_000) {
  await locator.waitFor({ state: "visible", timeout });
}

async function expectText(locator, expectedText, timeout = 15_000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    const text = await locator.textContent().catch(() => null);
    if (text === expectedText) {
      return;
    }
    await delay(200);
  }
  throw new Error(`Expected text "${expectedText}"`);
}

async function expectDisabled(locator, timeout = 15_000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await locator.isDisabled().catch(() => false)) {
      return;
    }
    await delay(200);
  }
  throw new Error("Expected locator to be disabled");
}

async function cleanupTemp() {
  await rm(`${backendTmpPrefix}.sqlite3`, { force: true });
  await rm(`${backendTmpPrefix}_uploads`, { force: true, recursive: true });
  await rm(`${backendTmpPrefix}_chroma`, { force: true, recursive: true });
}

function fixtureMarkdown() {
  return [
    "# 知识库上传",
    "",
    "知识库上传只支持 Markdown 文件，文件扩展名必须是 .md。",
    "处理完成后，文档进入有效目录，并可参与严格基于知识库的问答。",
    "",
    "# 问答边界",
    "",
    "知识库没有相关依据时，系统必须明确拒答，不允许使用外部搜索或常识补全。",
  ].join("\n");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function timestamp() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

function formatDuration(ms) {
  if (ms < 1000) {
    return `${ms} ms`;
  }
  return `${(ms / 1000).toFixed(2)} s`;
}

main().catch(async (error) => {
  await stopProcesses();
  await cleanupTemp();
  console.error(error);
  process.exit(1);
});
