(() => {
type StartBossCollectionMessage = {
  type: "AI_JOB_AGENT_START_BOSS_COLLECTION";
  sessionId: string;
  collectionToken: string;
  bossSearchUrl: string;
  backendBaseUrl: string;
  limit: number;
};

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

type ContentCollectionResponse = {
  ok: boolean;
  status?: "success" | "partial_success" | "failed";
  error_code?: string;
  error_message?: string;
  jobs?: CollectedJob[];
};

type DetailCollectionResponse = {
  ok: boolean;
  status?: "success" | "partial_success" | "failed";
  error_code?: string;
  error_message?: string;
  job?: Partial<CollectedJob>;
};

chrome.runtime.onInstalled.addListener(() => {
  console.info("ai-job-AGENT Boss Collector installed");
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!isObject(message) || typeof message.type !== "string") {
    return false;
  }

  if (message.type === "AI_JOB_AGENT_PING") {
    sendResponse({ ok: true, source: "ai-job-agent-extension", version: "0.1.0" });
    return true;
  }

  if (message.type === "AI_JOB_AGENT_START_BOSS_COLLECTION") {
    startBossCollection(message as StartBossCollectionMessage)
      .then((result) => sendResponse(result))
      .catch((error) =>
        sendResponse({
          ok: false,
          error_code: "EXTENSION_ERROR",
          error_message: error instanceof Error ? error.message : "扩展执行采集时发生未知错误。"
        })
      );
    return true;
  }

  return false;
});

async function startBossCollection(message: StartBossCollectionMessage) {
  if (!message.sessionId || !message.collectionToken || !message.bossSearchUrl) {
    return {
      ok: false,
      error_code: "INVALID_REQUEST",
      error_message: "采集参数不完整，请回到工作台重新开始。"
    };
  }

  const tabId = await openOrReuseBossTab(message.bossSearchUrl);
  const ready = await waitForBossSearchPage(tabId, message.bossSearchUrl);
  if (!ready) {
    return {
      ok: false,
      error_code: "PAGE_NOT_READY",
      error_message: "Boss 搜索页还没有切换到本次关键词，请稍等页面加载完成后重新采集。"
    };
  }

  const expectedQuery = expectedBossQuery(message.bossSearchUrl);
  const contentResponse = await waitAndCollectFromTab(tabId, message.limit, expectedQuery);

  const status = contentResponse.status ?? (contentResponse.ok ? "success" : "failed");
  const jobs = contentResponse.ok
    ? await enrichJobsWithDetails(contentResponse.jobs ?? [], message.limit)
    : contentResponse.jobs ?? [];
  const submitResponse = await fetch(
    `${message.backendBaseUrl}/job-collections/sessions/${message.sessionId}/jobs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        collection_token: message.collectionToken,
        jobs,
        status,
        error_code: contentResponse.error_code,
        error_message: contentResponse.error_message
      })
    }
  );

  if (!submitResponse.ok) {
    const text = await submitResponse.text();
    return {
      ok: false,
      error_code: "BACKEND_REJECTED",
      error_message: `后端拒绝了采集结果：${text}`
    };
  }

  const submitResult = await submitResponse.json();
  return {
    ok: contentResponse.ok,
    content_status: status,
    ...submitResult,
    error_code: contentResponse.error_code,
    error_message: contentResponse.error_message
  };
}

function openOrReuseBossTab(url: string): Promise<number> {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ url: "https://www.zhipin.com/*" }, (tabs) => {
      const existing = tabs.find((tab) => typeof tab.id === "number");
      if (existing?.id) {
        chrome.tabs.update(existing.id, { url, active: true }, () => resolve(existing.id as number));
        return;
      }

      chrome.tabs.create({ url, active: true }, (tab) => {
        if (!tab.id) {
          reject(new Error("无法打开 Boss 搜索页面，请确认浏览器允许扩展创建标签页。"));
          return;
        }
        resolve(tab.id);
      });
    });
  });
}

async function waitForBossSearchPage(tabId: number, expectedUrl: string) {
  const attempts = 24;
  for (let index = 0; index < attempts; index += 1) {
    const tab = await getTab(tabId);
    if (tab?.url && bossSearchUrlMatches(tab.url, expectedUrl)) {
      if (!tab.status || tab.status === "complete") {
        await delay(1600);
        return true;
      }
    }
    await delay(500);
  }
  return false;
}

async function waitAndCollectFromTab(
  tabId: number,
  limit: number,
  expectedQuery: string | null
): Promise<ContentCollectionResponse> {
  const attempts = 10;
  for (let index = 0; index < attempts; index += 1) {
    const response = await sendMessageToTab<ContentCollectionResponse>(tabId, {
      type: "AI_JOB_AGENT_COLLECT_VISIBLE_JOBS",
      limit,
      expectedQuery
    });

    if (response?.ok || response?.error_code === "AUTH_REQUIRED" || response?.error_code === "CAPTCHA_REQUIRED") {
      return response;
    }

    await delay(900);
  }

  return {
    ok: false,
    status: "failed",
    error_code: "SOURCE_CHANGED",
    error_message: "没有识别到 Boss 岗位卡片，可能是页面仍在加载或 Boss 页面结构已经变化。"
  };
}

function getTab(tabId: number): Promise<{ id?: number; url?: string; status?: string } | undefined> {
  return new Promise((resolve) => {
    chrome.tabs.get(tabId, (tab) => {
      if (chrome.runtime.lastError) {
        resolve(undefined);
        return;
      }
      resolve(tab);
    });
  });
}

function bossSearchUrlMatches(currentUrl: string, expectedUrl: string) {
  try {
    const current = new URL(currentUrl);
    const expected = new URL(expectedUrl);
    const currentQuery = current.searchParams.get("query")?.trim().toLowerCase();
    const expectedQuery = expected.searchParams.get("query")?.trim().toLowerCase();
    const currentCity = current.searchParams.get("city");
    const expectedCity = expected.searchParams.get("city");
    return (
      current.hostname.endsWith("zhipin.com") &&
      current.pathname.includes("/web/geek/job") &&
      currentQuery === expectedQuery &&
      (!expectedCity || currentCity === expectedCity)
    );
  } catch {
    return false;
  }
}

function expectedBossQuery(url: string) {
  try {
    return new URL(url).searchParams.get("query");
  } catch {
    return null;
  }
}

async function enrichJobsWithDetails(jobs: CollectedJob[], limit: number) {
  const enriched: CollectedJob[] = [];
  const targetJobs = jobs.slice(0, Math.max(1, Math.min(limit, 50)));
  const maxDetailFetches = Math.min(targetJobs.length, 20);

  for (const [index, job] of targetJobs.entries()) {
    if (index >= maxDetailFetches) {
      enriched.push(job);
      continue;
    }

    const detailUrl = normalizeBossUrl(job.job_url);
    if (!detailUrl) {
      enriched.push(job);
      continue;
    }

    const tabId = await openBackgroundTab(detailUrl);
    if (!tabId) {
      enriched.push(job);
      continue;
    }

    try {
      const detail = await waitAndExtractDetailFromTab(tabId);
      enriched.push(mergeJobDetail(job, detail?.job));
    } finally {
      closeTab(tabId);
      await delay(650);
    }
  }

  return enriched;
}

function openBackgroundTab(url: string): Promise<number | null> {
  return new Promise((resolve) => {
    chrome.tabs.create({ url, active: false }, (tab) => {
      resolve(typeof tab.id === "number" ? tab.id : null);
    });
  });
}

function closeTab(tabId: number) {
  chrome.tabs.remove(tabId);
}

async function waitAndExtractDetailFromTab(tabId: number): Promise<DetailCollectionResponse | undefined> {
  await delay(1200);
  const attempts = 5;
  for (let index = 0; index < attempts; index += 1) {
    const response = await sendMessageToTab<DetailCollectionResponse>(tabId, {
      type: "AI_JOB_AGENT_EXTRACT_BOSS_JOB_DETAIL"
    });
    if (response?.ok || response?.error_code === "AUTH_REQUIRED" || response?.error_code === "CAPTCHA_REQUIRED") {
      return response;
    }
    await delay(700);
  }
  return undefined;
}

function mergeJobDetail(base: CollectedJob, detail?: Partial<CollectedJob>): CollectedJob {
  if (!detail) return base;
  return {
    ...base,
    title: firstText(detail.title, base.title) ?? base.title,
    company: firstText(detail.company, base.company) ?? base.company,
    location: firstText(detail.location, base.location),
    salary: firstText(detail.salary, base.salary),
    experience: firstText(detail.experience, base.experience),
    education: firstText(detail.education, base.education),
    tags: uniqueTexts([...(base.tags ?? []), ...(detail.tags ?? [])]),
    job_url: firstText(detail.job_url, base.job_url),
    description: firstText(detail.description, base.description),
    source_job_id: firstText(detail.source_job_id, base.source_job_id)
  };
}

function firstText(...values: Array<string | null | undefined>) {
  return values.find((value) => value && value.trim().length > 0) ?? null;
}

function uniqueTexts(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function normalizeBossUrl(url: string | null | undefined) {
  if (!url) return null;
  try {
    return new URL(url, "https://www.zhipin.com").href;
  } catch {
    return url;
  }
}

function sendMessageToTab<T>(tabId: number, message: unknown): Promise<T | undefined> {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        resolve(undefined);
        return;
      }
      resolve(response as T);
    });
  });
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
})();
