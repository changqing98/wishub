import { expect, test } from "@playwright/test";
import { writeFile } from "node:fs/promises";

test("wishub MVP supports Markdown upload, catalog refresh, answer, refusal and clarification", async ({
  page,
}, testInfo) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "知识库" })).toBeVisible();
  await expect(page.getByText("当前暂无知识库文档")).toBeVisible();
  await expect(page.locator(".stat-card strong")).toHaveText("0");

  const invalidFile = testInfo.outputPath("not-markdown.txt");
  await writeFile(invalidFile, "not markdown");
  await page.locator('input[type="file"]').setInputFiles(invalidFile);
  await expect(page.getByText("仅支持 Markdown 文件（.md）")).toBeVisible();
  await expect(page.getByRole("button", { name: "上传并入库" })).toBeDisabled();

  const markdownFile = testInfo.outputPath("mvp-fixture.md");
  await writeFile(
    markdownFile,
    [
      "# 知识库上传",
      "",
      "知识库上传只支持 Markdown 文件，文件扩展名必须是 .md。",
      "处理完成后，文档进入有效目录，并可参与严格基于知识库的问答。",
      "",
      "# 问答边界",
      "",
      "知识库没有相关依据时，系统必须明确拒答，不允许使用外部搜索或常识补全。",
    ].join("\n"),
  );

  await page.locator('input[type="file"]').setInputFiles(markdownFile);
  await expect(page.getByText(/mvp-fixture\.md/).first()).toBeVisible();
  await page.getByRole("button", { name: "上传并入库" }).click();

  await expect(page.getByText(/mvp-fixture\.md 已加入知识库/)).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator(".stat-card strong")).toHaveText("1");
  await expect(page.getByText("mvp-fixture.md").first()).toBeVisible();
  await expect(page.getByText("可问答").first()).toBeVisible();

  await page.getByRole("button", { name: "知识问答" }).click();
  await expect(page.getByRole("heading", { name: "知识问答" })).toBeVisible();
  await expect(page.getByText("当前有效文档数：1")).toBeVisible();

  const questionBox = page.getByPlaceholder("输入一个关于知识库的问题…");
  await questionBox.fill("知识库上传支持什么格式？");
  await page.getByRole("button", { name: "提交问题" }).click();

  await expect(page.getByText("基于知识库的回答")).toBeVisible();
  await expect(page.getByRole("heading", { name: "引用依据" })).toBeVisible();
  await expect(page.getByText("外部知识：否")).toBeVisible();
  await expect(page.getByText("mvp-fixture.md").first()).toBeVisible();

  await questionBox.fill("明天北京天气怎么样？");
  await page.getByRole("button", { name: "提交问题" }).click();
  await expect(page.getByText("当前知识库暂无相关依据")).toBeVisible();

  await questionBox.fill("怎么做");
  await page.getByRole("button", { name: "提交问题" }).click();
  await expect(page.getByText("请补充问题信息")).toBeVisible();
});
