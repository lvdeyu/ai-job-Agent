import { useEffect, useMemo, useState } from "react";
import axios, { AxiosError } from "axios";
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Divider,
  Form,
  Input,
  InputNumber,
  Layout,
  List,
  Pagination,
  Select,
  Space,
  Tag,
  Typography,
  Upload
} from "antd";
import { Bot, BriefcaseBusiness, FileText, History, LogOut, Search, Settings, ShieldCheck, UserRound } from "lucide-react";

const { Header, Content } = Layout;
const { Title, Paragraph, Text } = Typography;

const API_BASE = "http://127.0.0.1:18000/api/v1";
type SectionKey = "config" | "job_search" | "history";
const DEFAULT_PROVIDER_BASE_URLS: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  tongyi: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  deepseek: "https://api.deepseek.com",
  claude: "https://api.anthropic.com/v1"
};

interface UserInfo {
  id: string;
  email: string;
  created_at: string;
}

interface Profile {
  target_role?: string;
  salary_min?: number;
  salary_max?: number;
  cities?: string;
  work_type?: "internship" | "full_time";
  deal_breakers?: string;
}

interface ModelProvider {
  id: string;
  provider: string;
  model_name: string;
  base_url?: string;
  timeout_seconds: number;
  network_mode: "auto" | "direct" | "manual_proxy";
  proxy_url?: string;
  masked_api_key: string;
}

interface ResumeVersion {
  id: string;
  title: string;
  version_no: number;
  extracted_text: string;
}

interface ResumeFile {
  id: string;
  original_filename: string;
  file_ext: string;
  file_size: number;
  is_default: boolean;
  versions: ResumeVersion[];
}

interface Job {
  id: string;
  title: string;
  company: string;
  location?: string;
  salary?: string;
  experience?: string;
  education?: string;
  tags?: string;
  job_url?: string;
  description?: string;
  is_in_pool: boolean;
  created_at: string;
}

interface JobEvaluationDimension {
  score: number;
  weight: number;
  data_status: "sufficient" | "insufficient_data";
  explanation: string;
}

interface JobEvaluationRequirements {
  required_skills?: string[];
  preferred_skills?: string[];
  matched_required_skills?: string[];
  missing_required_skills?: string[];
  matched_preferred_skills?: string[];
  missing_preferred_skills?: string[];
}

interface JobEvaluation {
  id: string;
  job_id: string;
  resume_version_id: string;
  resume_title?: string;
  framework_version: string;
  prompt_version: string;
  raw_weighted_score: number;
  final_score: number;
  recommendation: string;
  one_sentence_reason: string;
  language_gate_triggered: boolean;
  dealbreakers_hit: string[];
  dimensions: Record<string, JobEvaluationDimension>;
  highlights: string[];
  risks_and_gaps: string[];
  jd_requirements?: JobEvaluationRequirements;
  salary_benchmark: { value?: string; is_estimate?: boolean; evidence?: string };
  evidence: string[];
  resume_focus_suggestions: string[];
  honest_gap_statements: string[];
  created_at: string;
}

interface JobCollectionSession {
  id: string;
  keyword: string;
  city?: string;
  work_type?: "internship" | "full_time";
  limit: number;
  status: string;
  collection_token: string;
  token_expires_at: string;
  boss_search_url: string;
  error_code?: string;
  error_message?: string;
  accepted_count?: number;
  created_count?: number;
  duplicated_count?: number;
  filtered_count?: number;
  jobs: Job[];
}

interface JobCollectionSessionSummary {
  id: string;
  keyword: string;
  city?: string;
  work_type?: "internship" | "full_time";
  limit: number;
  status: string;
  boss_search_url: string;
  error_code?: string;
  error_message?: string;
  accepted_count: number;
  created_count: number;
  duplicated_count: number;
  filtered_count: number;
  job_count: number;
  created_at: string;
  updated_at: string;
}

interface JobCollectionHistoryPage {
  items: JobCollectionSessionSummary[];
  total: number;
  page: number;
  page_size: number;
}

interface ExtensionResponse {
  ok: boolean;
  created?: number;
  duplicated?: number;
  filtered?: number;
  accepted?: number;
  status?: string;
  error_code?: string;
  error_message?: string;
}

function errorMessage(error: unknown) {
  const axiosError = error as AxiosError<{ detail?: string }>;
  return axiosError.response?.data?.detail ?? axiosError.message ?? "请求失败";
}

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem("ai-job-agent-token") ?? "");
  const [user, setUser] = useState<UserInfo | null>(null);
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [resumes, setResumes] = useState<ResumeFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [networkMode, setNetworkMode] = useState<"auto" | "direct" | "manual_proxy">("auto");
  const [activeSection, setActiveSection] = useState<SectionKey>("job_search");
  const [extensionReady, setExtensionReady] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [collectionSession, setCollectionSession] = useState<JobCollectionSession | null>(null);
  const [evaluationsByJobId, setEvaluationsByJobId] = useState<Record<string, JobEvaluation>>({});
  const [evaluatingJobId, setEvaluatingJobId] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyData, setHistoryData] = useState<JobCollectionHistoryPage | null>(null);
  const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null);
  const [historyDetails, setHistoryDetails] = useState<Record<string, JobCollectionSession>>({});
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null);
  const [profileForm] = Form.useForm<Profile>();
  const [providerForm] = Form.useForm();
  const [jobSearchForm] = Form.useForm();

  const api = useMemo(
    () =>
      axios.create({
        baseURL: API_BASE,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      }),
    [token]
  );
  const displayedJobs = collectionSession?.jobs ?? [];
  const displayedJobIds = displayedJobs.map((job) => job.id).join("|");

  async function refreshWorkspace() {
    if (!token) return;
    const [me, profile, modelProviders, resumeList, jobList] = await Promise.all([
      api.get<UserInfo>("/auth/me"),
      api.get<Profile | null>("/profile"),
      api.get<ModelProvider[]>("/model-providers"),
      api.get<ResumeFile[]>("/resumes"),
      api.get<Job[]>("/jobs")
    ]);
    setUser(me.data);
    profileForm.setFieldsValue(profile.data ?? {});
    setProviders(modelProviders.data);
    setResumes(resumeList.data);
    setJobs(jobList.data);
  }

  useEffect(() => {
    if (!token) return;
    refreshWorkspace().catch((error) => {
      setMessage({ type: "error", text: errorMessage(error) });
      setToken("");
      localStorage.removeItem("ai-job-agent-token");
    });
  }, [token]);

  useEffect(() => {
    if (!token || displayedJobs.length === 0) return;
    loadLatestEvaluations(displayedJobs).catch(() => undefined);
  }, [token, displayedJobIds]);

  useEffect(() => {
    if (!token || activeSection !== "history") return;
    loadCollectionHistory(historyPage).catch((error) => {
      setMessage({ type: "error", text: errorMessage(error) });
    });
  }, [token, activeSection, historyPage]);

  useEffect(() => {
    function handleExtensionReady(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type === "AI_JOB_AGENT_EXTENSION_READY") {
        setExtensionReady(true);
      }
    }
    window.addEventListener("message", handleExtensionReady);
    pingExtension().catch(() => undefined);
    return () => window.removeEventListener("message", handleExtensionReady);
  }, []);

  async function handleAuth(values: { email: string; password: string }) {
    try {
      if (authMode === "register") {
        await axios.post(`${API_BASE}/auth/register`, values);
      }
      const response = await axios.post<{ access_token: string }>(`${API_BASE}/auth/login`, values);
      localStorage.setItem("ai-job-agent-token", response.data.access_token);
      setToken(response.data.access_token);
      setMessage({ type: "success", text: authMode === "register" ? "注册并登录成功" : "登录成功" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    }
  }

  async function saveProfile(values: Profile) {
    try {
      await api.put("/profile", values);
      setMessage({ type: "success", text: "个人求职配置已保存" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    }
  }

  async function saveProvider(values: Record<string, unknown>) {
    try {
      const provider = String(values.provider ?? "openai");
      const payload = {
        ...values,
        base_url: values.base_url || DEFAULT_PROVIDER_BASE_URLS[provider],
        proxy_url: values.network_mode === "manual_proxy" ? values.proxy_url : undefined
      };
      await api.post("/model-providers", payload);
      providerForm.resetFields();
      providerForm.setFieldsValue({
        provider: "openai",
        base_url: DEFAULT_PROVIDER_BASE_URLS.openai,
        timeout_seconds: 30,
        network_mode: "auto"
      });
      setNetworkMode("auto");
      await refreshWorkspace();
      setMessage({ type: "success", text: "AI 模型配置已保存" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    }
  }

  async function testProvider(providerId: string) {
    try {
      const response = await api.post(`/model-providers/${providerId}/test`);
      setMessage({
        type: response.data.ok ? "success" : "error",
        text: response.data.message
      });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    }
  }

  async function uploadResume() {
    if (!resumeFile) {
      setMessage({ type: "error", text: "请先选择 .docx、.md 或 .pdf 简历文件" });
      return;
    }
    try {
      const formData = new FormData();
      formData.append("file", resumeFile);
      await api.post("/resumes/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setResumeFile(null);
      await refreshWorkspace();
      setMessage({ type: "success", text: "简历上传并解析成功" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    }
  }

  async function pingExtension() {
    const response = await sendExtensionMessage<ExtensionResponse>({ type: "AI_JOB_AGENT_PING" }, 1200);
    setExtensionReady(Boolean(response.ok));
    return response;
  }

  async function startBossCollection(values: {
    keyword: string;
    city?: string;
    work_type?: "internship" | "full_time";
    limit: number;
  }) {
    setCollecting(true);
    setCollectionSession(null);
    setEvaluationsByJobId({});
    setMessage(null);
    try {
      const extension = await pingExtension();
      if (!extension.ok) {
        setMessage({
          type: "error",
          text: bossCollectionMessage(extension.error_code ?? "EXTENSION_REQUIRED", extension.error_message)
        });
        return;
      }

      const sessionResponse = await api.post<JobCollectionSession>("/job-collections/sessions", values);
      setCollectionSession(sessionResponse.data);
      const extensionResponse = await sendExtensionMessage<ExtensionResponse>(
        {
          type: "AI_JOB_AGENT_START_BOSS_COLLECTION",
          sessionId: sessionResponse.data.id,
          collectionToken: sessionResponse.data.collection_token,
          bossSearchUrl: sessionResponse.data.boss_search_url,
          backendBaseUrl: API_BASE,
          limit: sessionResponse.data.limit
        },
        120000
      );

      const refreshedSession = await api.get<JobCollectionSession>(
        `/job-collections/sessions/${sessionResponse.data.id}`
      );
      setCollectionSession(refreshedSession.data);
      setHistoryPage(1);
      await refreshWorkspace();
      await loadCollectionHistory(1);

      if (refreshedSession.data.status === "failed") {
        setMessage({
          type: "error",
          text: refreshedSession.data.error_message ?? "采集失败，请换一个更具体的关键词后重试。"
        });
        return;
      }

      if (!extensionResponse.ok && extensionResponse.error_code) {
        setMessage({
          type: "error",
          text: bossCollectionMessage(extensionResponse.error_code, extensionResponse.error_message)
        });
        return;
      }

      setMessage({
        type: "success",
        text: `采集完成：新增 ${extensionResponse.created ?? 0} 个，重复 ${
          extensionResponse.duplicated ?? 0
        } 个，过滤 ${extensionResponse.filtered ?? 0} 个不相关岗位。`
      });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setCollecting(false);
    }
  }

  async function loadCollectionHistory(page = historyPage) {
    if (!token) return;
    setHistoryLoading(true);
    try {
      const response = await api.get<JobCollectionHistoryPage>("/job-collections/sessions", {
        params: { page, page_size: 10 }
      });
      setHistoryData(response.data);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function openHistorySession(sessionId: string) {
    if (expandedHistoryId === sessionId) {
      setExpandedHistoryId(null);
      return;
    }
    setExpandedHistoryId(sessionId);
    if (historyDetails[sessionId]) {
      await loadLatestEvaluations(historyDetails[sessionId].jobs);
      return;
    }
    const response = await api.get<JobCollectionSession>(`/job-collections/sessions/${sessionId}`);
    setHistoryDetails((previous) => ({ ...previous, [sessionId]: response.data }));
    await loadLatestEvaluations(response.data.jobs);
  }

  async function deleteHistorySession(sessionId: string) {
    const confirmed = window.confirm("确定删除这条搜索历史吗？岗位数据和已有 AI 测评不会被删除。");
    if (!confirmed) return;

    setDeletingHistoryId(sessionId);
    try {
      await api.delete(`/job-collections/sessions/${sessionId}`);
      setHistoryDetails((previous) => {
        const next = { ...previous };
        delete next[sessionId];
        return next;
      });
      if (expandedHistoryId === sessionId) {
        setExpandedHistoryId(null);
      }

      const nextTotal = Math.max((historyData?.total ?? 1) - 1, 0);
      const nextPage = Math.min(historyPage, Math.max(Math.ceil(nextTotal / 10), 1));
      setHistoryPage(nextPage);
      await loadCollectionHistory(nextPage);
      setMessage({ type: "success", text: "搜索历史已删除，岗位数据和 AI 测评已保留。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setDeletingHistoryId(null);
    }
  }

  async function loadLatestEvaluations(jobList: Job[]) {
    const results = await Promise.all(
      jobList.map(async (job) => {
        try {
          const response = await api.get<JobEvaluation[]>(`/jobs/${job.id}/evaluations`);
          return [job.id, response.data[0]] as const;
        } catch {
          return [job.id, undefined] as const;
        }
      })
    );
    setEvaluationsByJobId((previous) => {
      const next = { ...previous };
      for (const [jobId, evaluation] of results) {
        if (evaluation) next[jobId] = evaluation;
      }
      return next;
    });
  }

  async function evaluateJob(jobId: string) {
    setEvaluatingJobId(jobId);
    try {
      const response = await api.post<JobEvaluation>(`/jobs/${jobId}/evaluations`, {});
      setEvaluationsByJobId((previous) => ({ ...previous, [jobId]: response.data }));
      setMessage({
        type: "success",
        text: `AI 测评完成：${response.data.final_score.toFixed(1)}/100，建议：${response.data.recommendation}`
      });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setEvaluatingJobId(null);
    }
  }

  function renderJobList(jobList: Job[], emptyText: string) {
    return (
      <List
        dataSource={jobList}
        locale={{ emptyText }}
        renderItem={(item) => {
          const evaluation = evaluationsByJobId[item.id];
          return (
            <List.Item
              actions={[
                <Button
                  key="evaluate"
                  type={evaluation ? "default" : "primary"}
                  loading={evaluatingJobId === item.id}
                  onClick={() => evaluateJob(item.id)}
                >
                  {evaluation ? "重新 AI 测评" : "AI 测评"}
                </Button>,
                <Button key="pool" disabled>
                  确认投递（V0.1-4）
                </Button>
              ]}
            >
              <List.Item.Meta
                title={
                  <Space wrap>
                    <a href={item.job_url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                    {item.is_in_pool && <Tag color="green">已入岗位池</Tag>}
                    {evaluation && <Tag color={evaluationTagColor(evaluation.final_score)}>{evaluation.recommendation}</Tag>}
                  </Space>
                }
                description={
                  <Space direction="vertical" size={8} className="job-meta-stack">
                    <Text>
                      {item.company}
                      {item.location ? ` / ${item.location}` : ""}
                      {item.salary ? ` / ${item.salary}` : ""}
                    </Text>
                    {item.tags && <Text type="secondary">标签：{item.tags}</Text>}
                    {evaluation && <EvaluationSummary evaluation={evaluation} />}
                  </Space>
                }
              />
            </List.Item>
          );
        }}
      />
    );
  }

  function logout() {
    localStorage.removeItem("ai-job-agent-token");
    setToken("");
    setUser(null);
    setProviders([]);
    setResumes([]);
    setJobs([]);
  }

  return (
    <ConfigProvider theme={{ token: { colorPrimary: "#1677ff", borderRadius: 8 } }}>
      <Layout className="app-shell">
        <Header className="app-header">
          <Space>
            <Bot size={22} />
            <Text className="brand">ai-job-AGENT</Text>
            <Tag color="blue">V0.1-2 Boss 采集</Tag>
          </Space>
          {user && (
            <Space>
              <Text>{user.email}</Text>
              <Button icon={<LogOut size={16} />} onClick={logout}>
                退出
              </Button>
            </Space>
          )}
        </Header>
        <Content className="app-content">
          {message && <Alert className="top-alert" type={message.type} message={message.text} showIcon closable />}

          {!token ? (
            <Card className="auth-card">
              <Space direction="vertical" size={4}>
                <Title level={2}>先创建你的本地求职工作台账号</Title>
                <Paragraph>V0.1 已开始支持多用户隔离，后续岗位、评测和面试都会挂到当前用户下。</Paragraph>
              </Space>
              <Form layout="vertical" onFinish={handleAuth}>
                <Form.Item name="email" label="邮箱" rules={[{ required: true, message: "请输入邮箱" }]}>
                  <Input prefix={<UserRound size={16} />} placeholder="student@example.com" />
                </Form.Item>
                <Form.Item name="password" label="密码" rules={[{ required: true, min: 8, message: "至少 8 位" }]}>
                  <Input.Password placeholder="至少 8 位密码" />
                </Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit">
                    {authMode === "register" ? "注册并登录" : "登录"}
                  </Button>
                  <Button type="link" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>
                    切换到{authMode === "login" ? "注册" : "登录"}
                  </Button>
                </Space>
              </Form>
            </Card>
          ) : (
            <div className="workspace-layout">
              <aside className="workspace-sidebar">
                <div className="sidebar-title">工作台</div>
                <button
                  className={`sidebar-item ${activeSection === "config" ? "active" : ""}`}
                  onClick={() => setActiveSection("config")}
                >
                  <Settings size={18} />
                  <span>基础配置</span>
                </button>
                <button
                  className={`sidebar-item ${activeSection === "job_search" ? "active" : ""}`}
                  onClick={() => setActiveSection("job_search")}
                >
                  <Search size={18} />
                  <span>岗位搜索</span>
                </button>
                <button
                  className={`sidebar-item ${activeSection === "history" ? "active" : ""}`}
                  onClick={() => setActiveSection("history")}
                >
                  <History size={18} />
                  <span>搜索历史</span>
                </button>
                <div className="sidebar-next">岗位池将在 V0.1-4 加入</div>
              </aside>
              <main className={`workspace-panel show-${activeSection}`}>
                <div className="section-hero">
                  <div>
                    <Title level={3}>{sectionTitle(activeSection)}</Title>
                    <Paragraph>{sectionDescription(activeSection)}</Paragraph>
                  </div>
                  <Tag color={extensionReady ? "green" : "orange"}>
                    {extensionReady ? "扩展已连接" : "扩展未连接"}
                  </Tag>
                </div>
                <div className="workspace-grid">
              <Card className="config-section" title={<CardTitle icon={<Settings size={18} />} text="个人求职配置" />}>
                <Form form={profileForm} layout="vertical" onFinish={saveProfile}>
                  <Form.Item name="target_role" label="意愿岗位">
                    <Input placeholder="Agent 开发实习生 / Java 后端实习生" />
                  </Form.Item>
                  <Space className="form-row" align="start">
                    <Form.Item name="salary_min" label="最低日薪">
                      <InputNumber min={0} addonAfter="元/天" />
                    </Form.Item>
                    <Form.Item name="salary_max" label="最高日薪">
                      <InputNumber min={0} addonAfter="元/天" />
                    </Form.Item>
                  </Space>
                  <Form.Item name="cities" label="工作城市">
                    <Input placeholder="杭州,上海,北京" />
                  </Form.Item>
                  <Form.Item name="work_type" label="工作形式">
                    <Select
                      allowClear
                      options={[
                        { value: "internship", label: "实习" },
                        { value: "full_time", label: "全职" }
                      ]}
                    />
                  </Form.Item>
                  <Form.Item name="deal_breakers" label="不能接受的条件">
                    <Input.TextArea rows={3} placeholder="例如：不接受无薪实习、不接受长期出差" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">
                    保存个人配置
                  </Button>
                </Form>
              </Card>

              <Card className="config-section" title={<CardTitle icon={<ShieldCheck size={18} />} text="AI 模型配置" />}>
                <Form
                  form={providerForm}
                  layout="vertical"
                  onFinish={saveProvider}
                  initialValues={{
                    provider: "openai",
                    base_url: DEFAULT_PROVIDER_BASE_URLS.openai,
                    network_mode: "auto",
                    timeout_seconds: 30
                  }}
                >
                  <Form.Item name="provider" label="供应商" rules={[{ required: true }]}>
                    <Select
                      onChange={(provider) => {
                        providerForm.setFieldValue("base_url", DEFAULT_PROVIDER_BASE_URLS[provider]);
                      }}
                      options={[
                        { value: "openai", label: "OpenAI" },
                        { value: "tongyi", label: "通义千问" },
                        { value: "deepseek", label: "DeepSeek" },
                        { value: "claude", label: "Claude" }
                      ]}
                    />
                  </Form.Item>
                  <Form.Item name="api_key" label="API Key" rules={[{ required: true }]}>
                    <Input.Password placeholder="不会在前端持久化完整密钥" />
                  </Form.Item>
                  <Form.Item name="model_name" label="模型名称" rules={[{ required: true }]}>
                    <Input placeholder="例如 gpt-4.1-mini / deepseek-chat / claude-3-5-sonnet-latest" />
                  </Form.Item>
                  <Form.Item name="base_url" label="Base URL">
                    <Input placeholder="DeepSeek 当前请使用 https://api.deepseek.com" />
                  </Form.Item>
                  <Form.Item
                    name="network_mode"
                    label="网络模式"
                    extra="自动：读取系统/环境代理；直连：强制不走代理；手动代理：填写本机代理地址。"
                  >
                    <Select
                      onChange={(value) => setNetworkMode(value)}
                      options={[
                        { value: "auto", label: "自动" },
                        { value: "direct", label: "直连" },
                        { value: "manual_proxy", label: "手动代理" }
                      ]}
                    />
                  </Form.Item>
                  {networkMode === "manual_proxy" && (
                    <Form.Item
                      name="proxy_url"
                      label="代理地址"
                      rules={[{ required: true, message: "选择手动代理时必须填写代理地址" }]}
                    >
                      <Input placeholder="例如 http://127.0.0.1:7890" />
                    </Form.Item>
                  )}
                  <Form.Item name="timeout_seconds" label="请求超时秒数">
                    <InputNumber min={3} max={120} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">
                    保存 AI 配置
                  </Button>
                </Form>
                <Divider />
                <List
                  locale={{ emptyText: "暂无模型配置" }}
                  dataSource={providers}
                  renderItem={(item) => (
                    <List.Item
                      actions={[
                        <Button key="test" onClick={() => testProvider(item.id)}>
                          连接测试
                        </Button>
                      ]}
                    >
                      <List.Item.Meta
                        title={`${item.provider} / ${item.model_name}`}
                        description={`Key: ${item.masked_api_key}，网络：${networkModeText(
                          item.network_mode
                        )}${item.proxy_url ? `（${item.proxy_url}）` : ""}，超时：${
                          item.timeout_seconds
                        }s`}
                      />
                    </List.Item>
                  )}
                />
              </Card>

              <Card className="wide-card config-section" title={<CardTitle icon={<FileText size={18} />} text="简历上传与默认简历" />}>
                <Upload.Dragger
                  accept=".docx,.md,.pdf"
                  maxCount={1}
                  beforeUpload={(file) => {
                    setResumeFile(file);
                    return false;
                  }}
                  onRemove={() => setResumeFile(null)}
                >
                  <p className="upload-title">点击或拖拽上传简历</p>
                  <p className="upload-desc">支持 .docx、.md、文本型 .pdf；扫描版 PDF 暂不支持 OCR。</p>
                </Upload.Dragger>
                <Button className="upload-button" type="primary" onClick={uploadResume}>
                  上传并解析
                </Button>
                <List
                  className="resume-list"
                  dataSource={resumes}
                  locale={{ emptyText: "暂无简历" }}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta
                        title={
                          <Space>
                            {item.original_filename}
                            {item.is_default && <Tag color="green">默认简历</Tag>}
                          </Space>
                        }
                        description={`大小 ${(item.file_size / 1024).toFixed(1)} KB，已提取 ${
                          item.versions[0]?.extracted_text.length ?? 0
                        } 字`}
                      />
                    </List.Item>
                  )}
                />
              </Card>

              <Card className="wide-card job-section" title={<CardTitle icon={<Search size={18} />} text="Boss 岗位搜索与采集" />}>
                <Alert
                  type={extensionReady ? "success" : "warning"}
                  showIcon
                  message={extensionReady ? "浏览器扩展已连接" : "未检测到浏览器扩展"}
                  description={
                    extensionReady
                      ? "采集会打开或复用 Boss 搜索页面，并顺序读取岗位详情页 JD；不读取 Boss 密码、Cookie 或聊天记录。"
                      : "请打开 Chrome/Edge 扩展管理页，启用开发者模式，加载 browser-extension/dist 目录，然后刷新本页面。"
                  }
                />
                <div className="collection-guide">
                  <Text strong>采集前请确认：</Text>
                  <ol>
                    <li>已经安装并启用 ai-job-AGENT 浏览器扩展。</li>
                    <li>已经在当前浏览器中登录 Boss 直聘。</li>
                    <li>如果 Boss 出现验证码或安全验证，请先手动完成。</li>
                    <li>采集过程中不要关闭 Boss 搜索页面。</li>
                  </ol>
                </div>
                <Form
                  form={jobSearchForm}
                  layout="vertical"
                  className="job-search-form"
                  initialValues={{ limit: 20 }}
                  onFinish={startBossCollection}
                >
                  <Space className="form-row" align="start">
                    <Form.Item name="keyword" label="岗位关键词" rules={[{ required: true, message: "请输入岗位关键词" }]}>
                      <Input placeholder="只填岗位关键词，例如 Agent / Python / Java 后端" />
                    </Form.Item>
                    <Form.Item name="city" label="城市">
                      <Input placeholder="杭州 / 上海 / 北京" />
                    </Form.Item>
                  </Space>
                  <Space className="form-row" align="start">
                    <Form.Item name="work_type" label="工作形式" extra="不会拼进 Boss 搜索框；采集回来后再筛选。">
                      <Select
                        allowClear
                        options={[
                          { value: "internship", label: "实习" },
                          { value: "full_time", label: "全职" }
                        ]}
                      />
                    </Form.Item>
                    <Form.Item name="limit" label="采集数量">
                      <Select
                        options={[
                          { value: 10, label: "10 个" },
                          { value: 20, label: "20 个（默认）" },
                          { value: 50, label: "50 个（上限）" }
                        ]}
                      />
                    </Form.Item>
                  </Space>
                  <Space>
                    <Button onClick={() => pingExtension()}>重新检测扩展</Button>
                    <Button
                      onClick={() => {
                        jobSearchForm.resetFields();
                        setCollectionSession(null);
                        setEvaluationsByJobId({});
                        setMessage(null);
                      }}
                    >
                      清空条件
                    </Button>
                    <Button type="primary" htmlType="submit" loading={collecting}>
                      开始采集 Boss 岗位
                    </Button>
                    {collectionSession && (
                      <Button href={collectionSession.boss_search_url} target="_blank">
                        打开 Boss 搜索页
                      </Button>
                    )}
                  </Space>
                </Form>
                {collectionSession && (
                  <Alert
                    className="collection-status"
                    type={collectionSession.status === "success" ? "success" : "info"}
                    showIcon
                    message={`本次采集结果：${collectionStatusText(collectionSession.status)}`}
                    description={
                      collectionSession.error_message ??
                      `本次搜索目标 ${collectionSession.limit} 个，已保存 ${collectionSession.jobs.length} 个岗位。`
                    }
                  />
                )}
              </Card>

              <Card className="wide-card job-section" title={<CardTitle icon={<BriefcaseBusiness size={18} />} text="岗位搜索结果" />}>
                {renderJobList(displayedJobs, "暂无本次采集结果。输入新关键词后开始采集。")}
              </Card>

              <Card className="wide-card history-section" title={<CardTitle icon={<History size={18} />} text="搜索历史" />}>
                <List
                  loading={historyLoading}
                  dataSource={historyData?.items ?? []}
                  locale={{ emptyText: "暂无搜索历史。完成一次岗位采集后会出现在这里。" }}
                  renderItem={(item) => {
                    const expanded = expandedHistoryId === item.id;
                    const detail = historyDetails[item.id];
                    return (
                      <List.Item
                        className="history-item"
                        actions={[
                          <Button key="open" onClick={() => openHistorySession(item.id)}>
                            {expanded ? "收起" : "展开岗位"}
                          </Button>,
                          <Button
                            key="delete"
                            danger
                            loading={deletingHistoryId === item.id}
                            onClick={() => deleteHistorySession(item.id)}
                          >
                            删除记录
                          </Button>
                        ]}
                      >
                        <div className="history-row">
                          <List.Item.Meta
                            title={
                              <Space wrap>
                                <Text strong>{item.keyword}</Text>
                                {item.city && <Tag>{item.city}</Tag>}
                                {item.work_type && <Tag>{workTypeText(item.work_type)}</Tag>}
                                <Tag color={item.status === "success" ? "green" : "orange"}>
                                  {collectionStatusText(item.status)}
                                </Tag>
                              </Space>
                            }
                            description={
                              <Space direction="vertical" size={4}>
                                <Text type="secondary">{formatDateTime(item.created_at)}</Text>
                                <Text type="secondary">{collectionStatsText(item)}</Text>
                              </Space>
                            }
                          />
                          {expanded && (
                            <div className="history-detail">
                              {detail
                                ? renderJobList(detail.jobs, "这次搜索没有可展示岗位。")
                                : <Text type="secondary">正在加载这次搜索的岗位...</Text>}
                            </div>
                          )}
                        </div>
                      </List.Item>
                    );
                  }}
                />
                <Pagination
                  className="history-pagination"
                  current={historyData?.page ?? historyPage}
                  total={historyData?.total ?? 0}
                  pageSize={10}
                  showSizeChanger={false}
                  onChange={(page) => setHistoryPage(page)}
                />
              </Card>
                </div>
              </main>
            </div>
          )}
        </Content>
      </Layout>
    </ConfigProvider>
  );
}

function CardTitle({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <Space>
      {icon}
      <span>{text}</span>
    </Space>
  );
}

function EvaluationSummary({ evaluation }: { evaluation: JobEvaluation }) {
  const dimensions = Object.entries(evaluation.dimensions);
  const requirements = evaluation.jd_requirements;
  const requiredSkills = requirements?.required_skills ?? [];
  const preferredSkills = requirements?.preferred_skills ?? [];
  const hasRequirements = requiredSkills.length > 0 || preferredSkills.length > 0;
  return (
    <div className="evaluation-panel">
      <div className="evaluation-header">
        <div>
          <Text strong>匹配度 {evaluation.final_score.toFixed(1)}/100</Text>
          <Text type="secondary"> · {evaluation.one_sentence_reason}</Text>
        </div>
        <Tag color={evaluationTagColor(evaluation.final_score)}>{evaluation.recommendation}</Tag>
      </div>
      <Space wrap size={[6, 6]} className="evaluation-dimensions">
        {dimensions.map(([key, dimension]) => (
          <Tag key={key}>
            {evaluationDimensionName(key)} {dimension.score.toFixed(0)}
            {dimension.data_status === "insufficient_data" ? "（信息不足）" : ""}
          </Tag>
        ))}
      </Space>
      {hasRequirements && (
        <div className="evaluation-block">
          <Text strong>JD 拆解：</Text>
          <div className="requirement-tags">
            {requiredSkills.map((skill) => (
              <Tag
                key={`required-${skill}`}
                color={requirements?.missing_required_skills?.includes(skill) ? "volcano" : "blue"}
              >
                必备 · {skill}
              </Tag>
            ))}
            {preferredSkills.map((skill) => (
              <Tag
                key={`preferred-${skill}`}
                color={requirements?.missing_preferred_skills?.includes(skill) ? "gold" : "green"}
              >
                加分 · {skill}
              </Tag>
            ))}
          </div>
        </div>
      )}
      {evaluation.risks_and_gaps.length > 0 && (
        <div className="evaluation-block">
          <Text strong>风险/缺口：</Text>
          <ul>
            {evaluation.risks_and_gaps.slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {evaluation.resume_focus_suggestions.length > 0 && (
        <div className="evaluation-block">
          <Text strong>简历建议：</Text>
          <ul>
            {evaluation.resume_focus_suggestions.slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      <Text type="secondary">
        框架 {evaluation.framework_version}，简历版本：{evaluation.resume_title ?? evaluation.resume_version_id}
      </Text>
    </div>
  );
}

function evaluationTagColor(score: number) {
  if (score >= 85) return "green";
  if (score >= 70) return "blue";
  if (score >= 50) return "orange";
  return "red";
}

function evaluationDimensionName(key: string) {
  const names: Record<string, string> = {
    skill_match: "技能",
    experience_match: "经验",
    behavioral_culture: "行为",
    compensation: "薪资",
    work_intensity: "强度",
    stability_compliance: "稳定",
    commute_city: "城市"
  };
  return names[key] ?? key;
}

function networkModeText(mode: ModelProvider["network_mode"]) {
  if (mode === "direct") return "直连";
  if (mode === "manual_proxy") return "手动代理";
  return "自动";
}


function sectionTitle(section: SectionKey) {
  if (section === "config") return "基础配置";
  if (section === "history") return "搜索历史";
  return "岗位搜索";
}

function sectionDescription(section: SectionKey) {
  if (section === "config") return "维护个人求职偏好、AI 模型和默认简历，后续评测都会读取这里的配置。";
  if (section === "history") return "按搜索时间倒序查看每次采集记录；展开后可继续 AI 测评或后续投递。";
  return "先按关键词从 Boss 直聘采集岗位，再按工作形式和相关性过滤结果。";
}

function workTypeText(workType: string) {
  if (workType === "internship") return "实习";
  if (workType === "full_time") return "全职";
  return workType;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function collectionStatsText(
  item: Pick<
    JobCollectionSessionSummary,
    "job_count" | "created_count" | "duplicated_count" | "filtered_count" | "accepted_count"
  >
) {
  return `展示 ${item.job_count} 个岗位 · 新增 ${item.created_count} · 重复 ${item.duplicated_count} · 过滤 ${item.filtered_count} · 接收 ${item.accepted_count}`;
}
function sendExtensionMessage<T>(payload: unknown, timeoutMs = 3000): Promise<T & { ok: boolean }> {
  const requestId = crypto.randomUUID();
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      window.removeEventListener("message", handleMessage);
      resolve({
        ok: false,
        error_code: "EXTENSION_REQUIRED",
        error_message: "没有收到浏览器扩展响应。"
      } as unknown as T & { ok: boolean });
    }, timeoutMs);

    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type !== "AI_JOB_AGENT_EXTENSION_TO_WEB" || event.data?.requestId !== requestId) return;
      window.clearTimeout(timer);
      window.removeEventListener("message", handleMessage);
      resolve(event.data.payload as T & { ok: boolean });
    }

    window.addEventListener("message", handleMessage);
    window.postMessage(
      {
        type: "AI_JOB_AGENT_WEB_TO_EXTENSION",
        requestId,
        payload
      },
      window.location.origin
    );
  });
}

function bossCollectionMessage(errorCode: string, fallback?: string) {
  const messages: Record<string, string> = {
    EXTENSION_REQUIRED: "没有检测到浏览器扩展。请加载 browser-extension/dist 后刷新本页面。",
    EXTENSION_CONTEXT_INVALIDATED: "扩展刚刚被重新加载，当前工作台页面里的旧脚本已失效。请刷新工作台页面后再试。",
    EXTENSION_BRIDGE_ERROR: "扩展通信失败。请先刷新工作台页面；如果刚更新过扩展，请在扩展管理页重新加载后再刷新本页面。",
    AUTH_REQUIRED: "Boss 当前未登录或登录已失效。请在 Boss 页面手动登录后重新采集。",
    CAPTCHA_REQUIRED: "Boss 要求验证码或安全验证。系统不会绕过验证，请你手动完成后重新采集。",
    SOURCE_CHANGED: "没有识别到岗位卡片，可能是 Boss 页面结构变化或页面尚未加载完成。",
    BACKEND_REJECTED: "后端拒绝了采集结果，请检查采集会话是否过期。",
    NO_RESULT: "当前搜索没有采集到有效岗位，可以换关键词或城市再试。"
  };
  return messages[errorCode] ?? fallback ?? "采集失败，请检查 Boss 页面状态后重试。";
}

function collectionStatusText(status: string) {
  const statusMap: Record<string, string> = {
    created: "已创建",
    success: "成功",
    partial_success: "部分成功",
    failed: "失败"
  };
  return statusMap[status] ?? status;
}








