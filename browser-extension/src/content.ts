(() => {
type CollectedJob = {
  title: string;
  company: string;
  location?: string | null;
  salary?: string | null;
  experience?: string | null;
  education?: string | null;
  tags?: string[];
  job_url?: string | null;
  description?: string | null;
  source_job_id?: string | null;
};

type WindowBridgeRequest = {
  type: "AI_JOB_AGENT_WEB_TO_EXTENSION";
  requestId: string;
  payload: unknown;
};

type WindowBridgeResponse = {
  type: "AI_JOB_AGENT_EXTENSION_TO_WEB";
  requestId: string;
  payload: unknown;
};

if (isLocalAppPage()) {
  window.addEventListener("message", (event) => {
    if (event.source !== window || !isObject(event.data)) return;
    const request = event.data as Partial<WindowBridgeRequest>;
    if (request.type !== "AI_JOB_AGENT_WEB_TO_EXTENSION" || !request.requestId) return;
    const requestId = request.requestId;

    try {
      chrome.runtime.sendMessage(request.payload, (response) => {
        const payload =
          chrome.runtime.lastError && !response
            ? {
                ok: false,
                error_code: "EXTENSION_BRIDGE_ERROR",
                error_message: chrome.runtime.lastError?.message ?? "扩展通信失败。"
              }
            : response ?? {
                ok: false,
                error_code: "EXTENSION_BRIDGE_ERROR",
                error_message: "扩展没有返回响应，请刷新工作台页面后重试。"
              };
        postBridgeResponse(requestId, payload);
      });
    } catch (error) {
      postBridgeResponse(requestId, {
        ok: false,
        error_code: "EXTENSION_CONTEXT_INVALIDATED",
        error_message:
          error instanceof Error && error.message.includes("Extension context invalidated")
            ? "扩展刚刚被重新加载，当前页面里的旧脚本已失效。请刷新工作台页面后重试。"
            : "扩展上下文不可用，请刷新工作台页面后重试。"
      });
    }
  });

  window.postMessage(
    {
      type: "AI_JOB_AGENT_EXTENSION_READY",
      source: "ai-job-agent-extension",
      version: "0.1.0"
    },
    window.location.origin
  );
}

function postBridgeResponse(requestId: string, payload: unknown) {
  const bridgeResponse: WindowBridgeResponse = {
    type: "AI_JOB_AGENT_EXTENSION_TO_WEB",
    requestId,
    payload
  };
  window.postMessage(bridgeResponse, window.location.origin);
}

if (isBossPage()) {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!isObject(message)) {
      return false;
    }

    if (message.type === "AI_JOB_AGENT_COLLECT_VISIBLE_JOBS") {
      const limit = normalizeLimit(message.limit);
      const expectedQuery =
        typeof message.expectedQuery === "string" ? message.expectedQuery.trim() : null;
      sendResponse(collectVisibleBossJobs(limit, expectedQuery));
      return true;
    }

    if (message.type === "AI_JOB_AGENT_EXTRACT_BOSS_JOB_DETAIL") {
      sendResponse(extractBossJobDetail());
      return true;
    }

    return true;
  });
}

function collectVisibleBossJobs(limit: number, expectedQuery: string | null) {
  const normalizedExpectedQuery = expectedQuery?.toLowerCase() ?? null;
  if (normalizedExpectedQuery && !isCurrentBossSearchSettled(normalizedExpectedQuery)) {
    return {
      ok: false,
      status: "failed",
      error_code: "PAGE_NOT_READY",
      error_message: "Boss 页面还没有切换到本次搜索关键词，请等待页面加载完成后重试。"
    };
  }

  if (document.body.innerText.includes("验证码") || document.body.innerText.includes("安全验证")) {
    return {
      ok: false,
      status: "failed",
      error_code: "CAPTCHA_REQUIRED",
      error_message: "Boss 当前要求验证码或安全验证，请手动完成后回到工作台重新采集。"
    };
  }

  if (looksLikeLoginPage()) {
    return {
      ok: false,
      status: "failed",
      error_code: "AUTH_REQUIRED",
      error_message: "Boss 当前未登录或登录已失效，请在 Boss 页面手动登录后重新采集。"
    };
  }

  const cards = findJobCards();
  const jobs = uniqueJobs(cards.map(parseJobCard).filter((job): job is CollectedJob => Boolean(job))).slice(0, limit);

  if (jobs.length === 0) {
    return {
      ok: false,
      status: "failed",
      error_code: cards.length === 0 ? "SOURCE_CHANGED" : "NO_RESULT",
      error_message:
        cards.length === 0
          ? "没有识别到 Boss 岗位卡片，可能是页面结构变化或搜索页尚未加载完成。"
          : "当前 Boss 页面没有可采集的有效岗位。"
    };
  }

  return {
    ok: true,
    status: jobs.length < limit ? "partial_success" : "success",
    jobs
  };
}

function currentBossQuery() {
  try {
    return new URL(location.href).searchParams.get("query")?.trim().toLowerCase() ?? "";
  } catch {
    return "";
  }
}

function isCurrentBossSearchSettled(expectedQuery: string) {
  if (currentBossQuery() !== expectedQuery) return false;
  const searchInputValue = currentBossSearchInputValue();
  return !searchInputValue || searchInputValue === expectedQuery;
}

function currentBossSearchInputValue() {
  const selectors = [
    "input[name='query']",
    "input[name='keyword']",
    ".search-form input",
    ".search-input input",
    "input[placeholder*='职位']",
    "input[placeholder*='搜索']"
  ];
  for (const selector of selectors) {
    const input = document.querySelector<HTMLInputElement>(selector);
    const value = input?.value?.trim().toLowerCase();
    if (value) return value;
  }
  return null;
}

function findJobCards(): Element[] {
  const selectors = [
    ".job-card-wrap",
    ".job-card-wrapper",
    ".job-card-box",
    ".job-card-body",
    ".search-job-result .job-card-wrap",
    ".job-list-box li",
    "li[class*='job-card']",
    "div[class*='job-card']"
  ];
  const elements = selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
  return uniqueElements(elements).filter((element) => {
    const text = element.textContent?.trim() ?? "";
    return text.length > 10 && Boolean(findFirstText(element, [".job-name", "[class*='job-name']"]));
  });
}

function parseJobCard(card: Element): CollectedJob | null {
  const title = findFirstText(card, [".job-name", "[class*='job-name']", "a[href*='job_detail']", "a"]);
  const company = findFirstText(card, [".company-name", "[class*='company-name']", ".boss-name"]);
  if (!title || !company) return null;

  const link = card.querySelector<HTMLAnchorElement>("a[href*='job_detail']");
  const href = normalizeBossUrl(link?.href ?? link?.getAttribute("href") ?? null);
  const tags = Array.from(card.querySelectorAll(".tag-list li, [class*='tag'] li, .job-card-footer li"))
    .map((node) => node.textContent?.trim() ?? "")
    .filter(Boolean)
    .slice(0, 12);

  return {
    title,
    company,
    location: findFirstText(card, [".job-area", "[class*='job-area']", ".job-location"]),
    salary: findFirstText(card, [".salary", "[class*='salary']"]),
    experience: findFirstText(card, [".job-info .tag-list li:nth-child(1)", ".job-card-footer li:nth-child(1)"]),
    education: findFirstText(card, [".job-info .tag-list li:nth-child(2)", ".job-card-footer li:nth-child(2)"]),
    tags,
    job_url: href,
    description: card.textContent?.replace(/\s+/g, " ").trim().slice(0, 4000) ?? null,
    source_job_id: extractJobId(href)
  };
}

function extractBossJobDetail() {
  if (document.body.innerText.includes("验证码") || document.body.innerText.includes("安全验证")) {
    return {
      ok: false,
      status: "failed",
      error_code: "CAPTCHA_REQUIRED",
      error_message: "Boss 当前要求验证码或安全验证，请手动完成后重新采集。"
    };
  }

  if (looksLikeLoginPage()) {
    return {
      ok: false,
      status: "failed",
      error_code: "AUTH_REQUIRED",
      error_message: "Boss 当前未登录或登录已失效，请在 Boss 页面手动登录后重新采集。"
    };
  }

  const jd = findFirstText(document, [
    ".job-sec-text",
    ".job-detail-section .text",
    ".job-detail .job-sec-text",
    "[class*='job-sec-text']"
  ]);
  const detailText = findFirstText(document, [
    ".job-detail",
    ".job-detail-box",
    ".job-detail-container",
    ".job-primary",
    "main"
  ]);
  const title = findFirstText(document, [
    ".info-primary .name h1",
    ".job-primary h1",
    ".name h1",
    "h1"
  ]);
  const salary = findFirstText(document, [".info-primary .salary", ".job-primary .salary", ".salary"]);
  const company = findFirstText(document, [
    ".sider-company .company-info a",
    ".sider-company a[href*='gongsi']",
    ".company-name",
    "[class*='company-name']"
  ]);
  const jobLocation = findFirstText(document, [".text-city", ".job-primary .text-city", "[class*='text-city']"]);
  const experience = findFirstText(document, [
    ".text-experiece",
    ".text-experience",
    ".job-primary .tag-list span:nth-child(1)",
    ".info-primary .tag-list span:nth-child(1)"
  ]);
  const education = findFirstText(document, [
    ".text-degree",
    ".job-primary .tag-list span:nth-child(2)",
    ".info-primary .tag-list span:nth-child(2)"
  ]);
  const tags = Array.from(
    document.querySelectorAll(
      ".job-primary .tag-list span, .info-primary .tag-list span, .job-tags span, .job-sec .tag-list span"
    )
  )
    .map((node) => compactText(node.textContent))
    .filter(Boolean)
    .slice(0, 16);

  const description = compactText([jd, detailText].filter(Boolean).join("\n\n")).slice(0, 8000);
  const fallbackTitle = document.title.split("-")[0]?.trim() || null;
  const finalTitle = title || fallbackTitle;

  if (!finalTitle && !description) {
    return {
      ok: false,
      status: "failed",
      error_code: "SOURCE_CHANGED",
      error_message: "详情页已打开，但没有识别到岗位详情内容。"
    };
  }

  return {
    ok: true,
    status: "success",
    job: {
      title: finalTitle,
      company,
      location: jobLocation,
      salary,
      experience,
      education,
      tags: uniqueTexts(tags),
      job_url: window.location.href,
      description,
      source_job_id: extractJobId(window.location.href)
    }
  };
}

function findFirstText(root: ParentNode, selectors: string[]): string | null {
  for (const selector of selectors) {
    const text = compactText(root.querySelector(selector)?.textContent);
    if (text) return text;
  }
  return null;
}

function compactText(value: string | null | undefined) {
  return value?.replace(/\s+/g, " ").trim() ?? "";
}

function normalizeBossUrl(url: string | null) {
  if (!url) return null;
  try {
    return new URL(url, location.origin).href;
  } catch {
    return url;
  }
}

function extractJobId(url: string | null) {
  if (!url) return null;
  const match = url.match(/job_detail\/([^./?]+)/);
  return match?.[1] ?? null;
}

function looksLikeLoginPage() {
  const text = document.body.innerText;
  return (
    location.href.includes("/web/user/") ||
    (text.includes("登录") && text.includes("注册") && !text.includes("职位"))
  );
}

function normalizeLimit(value: unknown) {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return 20;
  return Math.max(1, Math.min(50, Math.floor(parsed)));
}

function uniqueElements(elements: Element[]) {
  return Array.from(new Set(elements));
}

function uniqueTexts(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function uniqueJobs(jobs: CollectedJob[]) {
  const seen = new Set<string>();
  return jobs.filter((job) => {
    const key = job.source_job_id || job.job_url || `${job.title}|${job.company}|${job.salary ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isLocalAppPage() {
  return location.origin === "http://127.0.0.1:15173" || location.origin === "http://localhost:15173";
}

function isBossPage() {
  return location.hostname.endsWith("zhipin.com");
}
})();
