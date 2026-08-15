import { useEffect, useMemo, useState } from "react";
import axios, { AxiosError } from "axios";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  ConfigProvider,
  Divider,
  Form,
  Input,
  InputNumber,
  Layout,
  List,
  Modal,
  Pagination,
  Select,
  Space,
  Tag,
  Typography,
  Upload
} from "antd";
import { Bot, BriefcaseBusiness, FileText, History, LogOut, MessageSquareText, Search, Settings, ShieldCheck, Trash2, UploadCloud, UserRound } from "lucide-react";

const { Header, Content } = Layout;
const { Title, Paragraph, Text } = Typography;

const API_BASE = "http://127.0.0.1:18000/api/v1";
const APPLICATION_STATUS_OPTIONS = [
  { value: "NEW", label: "待处理" },
  { value: "SCORED", label: "已评测" },
  { value: "REVIEWED", label: "已复盘" },
  { value: "CONFIRMED", label: "准备投递" },
  { value: "APPLIED", label: "已投递" },
  { value: "INTERVIEWING", label: "面试中" },
  { value: "OFFER", label: "Offer" },
  { value: "REJECTED", label: "已拒绝" },
  { value: "ARCHIVED", label: "已归档" }
];

const APPLICATION_STATUS_COLORS: Record<string, string> = {
  NEW: "default",
  SCORED: "blue",
  REVIEWED: "cyan",
  CONFIRMED: "geekblue",
  APPLIED: "green",
  INTERVIEWING: "purple",
  OFFER: "gold",
  REJECTED: "red",
  ARCHIVED: "default"
};

function applicationStatusText(status?: string) {
  return APPLICATION_STATUS_OPTIONS.find((option) => option.value === status)?.label ?? "待处理";
}

function applicationStatusColor(status?: string) {
  return status ? APPLICATION_STATUS_COLORS[status] ?? "default" : "default";
}

type SectionKey =
  | "config"
  | "job_search"
  | "history"
  | "job_pool"
  | "interview"
  | "interview_history"
  | "tasks";
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
  source_type: "uploaded" | "job_copy" | "job_upload";
  source_version_id?: string;
  job_id?: string;
  created_at: string;
  updated_at?: string;
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
  application_status: string;
  applied_at?: string;
  application_resume_version_id?: string;
  application_resume_title?: string;
  contact_name?: string;
  notes?: string;
  status_changed_at?: string;
  has_interviewed: boolean;
  created_at: string;
}

type JobPoolItemPatch = Partial<Pick<Job, "application_status">> & {
  applied_at?: string | null;
  application_resume_version_id?: string | null;
  notes?: string | null;
};

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
  resume_source_type?: string;
  framework_version: string;
  prompt_version: string;
  output_schema_version: string;
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
  adapter_name: string;
  adapter_enabled_snapshot: boolean;
  extension_version?: string;
  page_limit: number;
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
  adapter_name: string;
  adapter_enabled_snapshot: boolean;
  extension_version?: string;
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

interface JobCollectionAdapterStatus {
  name: string;
  enabled: boolean;
  min_extension_version: string;
  max_page_limit: number;
  rate_limit_window_seconds: number;
  rate_limit_max_sessions: number;
  detail: string;
}

interface InterviewTurn {
  id: string;
  turn_index: number;
  question_text: string;
  question_type: string;
  skill_tags: string[];
  is_followup: boolean;
  followup_depth: number;
  answer_text?: string;
  score?: number;
  feedback?: string;
  evidence: string[];
  status: string;
  question_bank_item_external_id?: string;
}

interface InterviewSession {
  id: string;
  job_id: string;
  job_title: string;
  company: string;
  resume_version_id: string;
  resume_title?: string;
  job_evaluation_id?: string;
  status: "running" | "completed";
  retrieval_mode: string;
  scoring_mode: string;
  max_questions: number;
  main_questions_answered: number;
  current_turn?: InterviewTurn;
  turns: InterviewTurn[];
  report?: InterviewReport;
  checkpoint: {
    mode: string;
    status: string;
    resume_session_id: string;
    current_turn_id?: string;
    answered_turn_count: number;
  };
}

interface InterviewHistoryItem {
  id: string;
  job_id: string;
  job_title: string;
  company: string;
  location?: string;
  salary?: string;
  status: "running" | "completed";
  total_score?: number;
  question_count: number;
  main_questions_answered: number;
  created_at: string;
  completed_at?: string;
}

interface TaskStatusItem {
  name: string;
  status: string;
  backend: string;
  detail: string;
  updated_at?: string;
}

interface ExtensionResponse {
  ok: boolean;
  version?: string;
  created?: number;
  duplicated?: number;
  filtered?: number;
  accepted?: number;
  status?: string;
  error_code?: string;
  error_message?: string;
}

function errorMessage(error: unknown) {
  const axiosError = error as AxiosError<{
    detail?: string;
    error?: { message?: string; request_id?: string };
  }>;
  const apiError = axiosError.response?.data?.error;
  if (apiError?.message) {
    return apiError.request_id ? `${apiError.message}（request_id: ${apiError.request_id}）` : apiError.message;
  }
  return axiosError.response?.data?.detail ?? axiosError.message ?? "请求失败";
}

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem("ai-job-agent-token") ?? "");
  const [user, setUser] = useState<UserInfo | null>(null);
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [resumes, setResumes] = useState<ResumeFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobPool, setJobPool] = useState<Job[]>([]);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [networkMode, setNetworkMode] = useState<"auto" | "direct" | "manual_proxy">("auto");
  const [activeSection, setActiveSection] = useState<SectionKey>("job_search");
  const [extensionReady, setExtensionReady] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [collectionSession, setCollectionSession] = useState<JobCollectionSession | null>(null);
  const [evaluationsByJobId, setEvaluationsByJobId] = useState<Record<string, JobEvaluation>>({});
  const [evaluationHistoriesByJobId, setEvaluationHistoriesByJobId] = useState<Record<string, JobEvaluation[]>>({});
  const [evaluatingJobId, setEvaluatingJobId] = useState<string | null>(null);
  const [jobResumeModalJob, setJobResumeModalJob] = useState<Job | null>(null);
  const [jobResumeFile, setJobResumeFile] = useState<File | null>(null);
  const [jobResumeUploadError, setJobResumeUploadError] = useState<string | null>(null);
  const [uploadingJobResumeId, setUploadingJobResumeId] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyData, setHistoryData] = useState<JobCollectionHistoryPage | null>(null);
  const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null);
  const [historyDetails, setHistoryDetails] = useState<Record<string, JobCollectionSession>>({});
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null);
  const [selectedHistoryIds, setSelectedHistoryIds] = useState<string[]>([]);
  const [deletingHistoryBatch, setDeletingHistoryBatch] = useState(false);
  const [jobPoolLoading, setJobPoolLoading] = useState(false);
  const [addingToPoolJobId, setAddingToPoolJobId] = useState<string | null>(null);
  const [jobPoolFilter, setJobPoolFilter] = useState("");
  const [jobPoolStatusFilter, setJobPoolStatusFilter] = useState<string | undefined>();
  const [jobPoolCompanyFilter, setJobPoolCompanyFilter] = useState("");
  const [jobPoolCityFilter, setJobPoolCityFilter] = useState("");
  const [selectedJobPoolIds, setSelectedJobPoolIds] = useState<string[]>([]);
  const [removingJobPoolBatch, setRemovingJobPoolBatch] = useState(false);
  const [savingJobPoolItemId, setSavingJobPoolItemId] = useState<string | null>(null);
  const [profileDirty, setProfileDirty] = useState(false);
  const [providerDirty, setProviderDirty] = useState(false);
  const [deletingProviderId, setDeletingProviderId] = useState<string | null>(null);
  const [deletingResumeId, setDeletingResumeId] = useState<string | null>(null);
  const [settingDefaultResumeId, setSettingDefaultResumeId] = useState<string | null>(null);
  const [activeInterview, setActiveInterview] = useState<InterviewSession | null>(null);
  const [interviewHistory, setInterviewHistory] = useState<InterviewHistoryItem[]>([]);
  const [interviewHistoryLoading, setInterviewHistoryLoading] = useState(false);
  const [interviewLoadingJobId, setInterviewLoadingJobId] = useState<string | null>(null);
  const [loadingInterviewDetailId, setLoadingInterviewDetailId] = useState<string | null>(null);
  const [selectedInterviewHistoryIds, setSelectedInterviewHistoryIds] = useState<string[]>([]);
  const [deletingInterviewHistoryId, setDeletingInterviewHistoryId] = useState<string | null>(null);
  const [deletingInterviewHistoryBatch, setDeletingInterviewHistoryBatch] = useState(false);
  const [taskStatuses, setTaskStatuses] = useState<TaskStatusItem[]>([]);
  const [taskStatusesLoading, setTaskStatusesLoading] = useState(false);
  const [answerSubmitting, setAnswerSubmitting] = useState(false);
  const [profileForm] = Form.useForm<Profile>();
  const [providerForm] = Form.useForm();
  const [jobSearchForm] = Form.useForm();
  const [interviewAnswerForm] = Form.useForm<{ answer_text: string }>();

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
  const allResumeVersions = useMemo(
    () => resumes.flatMap((resume) => resume.versions.map((version) => ({ ...version, resumeFileId: resume.id }))),
    [resumes]
  );
  const defaultResumeVersion = useMemo(() => {
    const defaultResume = resumes.find((resume) => resume.is_default);
    const defaultUploadedVersions = defaultResume?.versions.filter((version) => version.source_type === "uploaded") ?? [];
    return (
      defaultUploadedVersions[defaultUploadedVersions.length - 1] ??
      allResumeVersions.find((version) => version.source_type === "uploaded")
    );
  }, [allResumeVersions, resumes]);
  const baseResumeFiles = useMemo(
    () => resumes.filter((resume) => resume.versions.some((version) => version.source_type === "uploaded")),
    [resumes]
  );
  const historyPageIds = historyData?.items.map((item) => item.id) ?? [];
  const selectedHistoryIdsOnPage = historyPageIds.filter((id) => selectedHistoryIds.includes(id));
  const isHistoryPageFullySelected =
    historyPageIds.length > 0 && selectedHistoryIdsOnPage.length === historyPageIds.length;
  const isHistoryPagePartiallySelected =
    selectedHistoryIdsOnPage.length > 0 && selectedHistoryIdsOnPage.length < historyPageIds.length;
  const filteredJobPool = useMemo(() => {
    const keyword = jobPoolFilter.trim().toLowerCase();
    const company = jobPoolCompanyFilter.trim().toLowerCase();
    const city = jobPoolCityFilter.trim().toLowerCase();
    return jobPool.filter((job) =>
      (!jobPoolStatusFilter || job.application_status === jobPoolStatusFilter) &&
      (!company || (job.company ?? "").toLowerCase().includes(company)) &&
      (!city || (job.location ?? "").toLowerCase().includes(city)) &&
      (!keyword ||
        [job.title, job.company, job.location, job.salary, job.tags, job.description]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(keyword))
    );
  }, [jobPool, jobPoolCityFilter, jobPoolCompanyFilter, jobPoolFilter, jobPoolStatusFilter]);
  const filteredJobPoolIds = filteredJobPool.map((job) => job.id);
  const selectedJobPoolIdsOnPage = filteredJobPoolIds.filter((id) => selectedJobPoolIds.includes(id));
  const isJobPoolFullySelected =
    filteredJobPoolIds.length > 0 && selectedJobPoolIdsOnPage.length === filteredJobPoolIds.length;
  const isJobPoolPartiallySelected =
    selectedJobPoolIdsOnPage.length > 0 && selectedJobPoolIdsOnPage.length < filteredJobPoolIds.length;
  const interviewHistoryIds = interviewHistory.map((item) => item.id);
  const selectedInterviewHistoryIdsOnPage = interviewHistoryIds.filter((id) =>
    selectedInterviewHistoryIds.includes(id)
  );
  const isInterviewHistoryFullySelected =
    interviewHistoryIds.length > 0 && selectedInterviewHistoryIdsOnPage.length === interviewHistoryIds.length;
  const isInterviewHistoryPartiallySelected =
    selectedInterviewHistoryIdsOnPage.length > 0 &&
    selectedInterviewHistoryIdsOnPage.length < interviewHistoryIds.length;

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
    setJobPool(jobList.data.filter((job) => job.is_in_pool));
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
    if (!token || activeSection !== "job_pool") return;
    loadJobPool().catch((error) => {
      setMessage({ type: "error", text: errorMessage(error) });
    });
  }, [token, activeSection, jobPoolFilter, jobPoolStatusFilter, jobPoolCompanyFilter, jobPoolCityFilter]);

  useEffect(() => {
    if (!token || activeSection !== "interview_history") return;
    loadInterviewHistory().catch((error) => {
      setMessage({ type: "error", text: errorMessage(error) });
    });
  }, [token, activeSection]);

  useEffect(() => {
    if (!token || activeSection !== "tasks") return;
    loadTaskStatuses().catch((error) => {
      setMessage({ type: "error", text: errorMessage(error) });
    });
  }, [token, activeSection]);

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
      setProfileDirty(false);
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
      setProviderDirty(false);
      setNetworkMode(values.network_mode as ModelProvider["network_mode"]);
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

  async function deleteProvider(providerId: string) {
    const confirmed = window.confirm("确定删除这个 AI 模型配置吗？删除后不会影响已经生成的历史评测。");
    if (!confirmed) return;

    setDeletingProviderId(providerId);
    try {
      await api.delete(`/model-providers/${providerId}`);
      await refreshWorkspace();
      setMessage({ type: "success", text: "AI 模型配置已删除。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setDeletingProviderId(null);
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

  async function setDefaultResume(resumeId: string) {
    setSettingDefaultResumeId(resumeId);
    try {
      await api.post(`/resumes/${resumeId}/set-default`);
      await refreshWorkspace();
      setMessage({ type: "success", text: "默认简历已更新。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setSettingDefaultResumeId(null);
    }
  }

  async function deleteResume(resumeId: string) {
    const confirmed = window.confirm(
      "确定删除这份简历吗？该简历版本关联的历史 AI 测评也会一并删除；上传新简历后可以重新测评。"
    );
    if (!confirmed) return;

    setDeletingResumeId(resumeId);
    try {
      await api.delete(`/resumes/${resumeId}`);
      await refreshWorkspace();
      setMessage({ type: "success", text: "简历已删除。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setDeletingResumeId(null);
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
    setEvaluationHistoriesByJobId({});
    setMessage(null);
    try {
      const adapterStatus = await api.get<JobCollectionAdapterStatus>("/job-collections/adapter-status");
      if (!adapterStatus.data.enabled) {
        setMessage({ type: "error", text: adapterStatus.data.detail });
        return;
      }

      const extension = await pingExtension();
      if (!extension.ok) {
        setMessage({
          type: "error",
          text: bossCollectionMessage(extension.error_code ?? "EXTENSION_REQUIRED", extension.error_message)
        });
        return;
      }

      const idempotencyKey = crypto.randomUUID();
      const extensionVersion = extension.version ?? "0.1.0";
      const sessionResponse = await api.post<JobCollectionSession>("/job-collections/sessions", {
        ...values,
        idempotency_key: idempotencyKey,
        extension_version: extensionVersion
      });
      setCollectionSession(sessionResponse.data);
      const extensionResponse = await sendExtensionMessage<ExtensionResponse>(
        {
          type: "AI_JOB_AGENT_START_BOSS_COLLECTION",
          sessionId: sessionResponse.data.id,
          collectionToken: sessionResponse.data.collection_token,
          bossSearchUrl: sessionResponse.data.boss_search_url,
          backendBaseUrl: API_BASE,
          limit: sessionResponse.data.limit,
          pageLimit: sessionResponse.data.page_limit,
          idempotencyKey,
          extensionVersion
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

      if (["failed", "AUTH_REQUIRED", "CAPTCHA_REQUIRED", "RATE_LIMITED", "SOURCE_CHANGED"].includes(
        refreshedSession.data.status
      )) {
        setMessage({
          type: "error",
          text:
            refreshedSession.data.error_message ??
            bossCollectionMessage(refreshedSession.data.error_code ?? refreshedSession.data.status)
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

  async function loadJobPool() {
    if (!token) return;
    setJobPoolLoading(true);
    try {
      const [response, resumeResponse] = await Promise.all([
        api.get<Job[]>("/jobs/pool", {
          params: {
            status: jobPoolStatusFilter,
            keyword: jobPoolFilter || undefined,
            company: jobPoolCompanyFilter || undefined,
            city: jobPoolCityFilter || undefined
          }
        }),
        api.get<ResumeFile[]>("/resumes")
      ]);
      setJobPool(response.data);
      setResumes(resumeResponse.data);
      setSelectedJobPoolIds((previous) =>
        previous.filter((id) => response.data.some((job) => job.id === id))
      );
      await loadLatestEvaluations(response.data);
    } finally {
      setJobPoolLoading(false);
    }
  }

  async function removeSelectedJobsFromPool() {
    if (selectedJobPoolIds.length === 0) {
      setMessage({ type: "error", text: "请先选择要移出岗位池的岗位。" });
      return;
    }
    const confirmed = window.confirm(
      `确定将选中的 ${selectedJobPoolIds.length} 个岗位移出岗位池吗？岗位数据、AI 测评和面试历史都会保留。`
    );
    if (!confirmed) return;
    setRemovingJobPoolBatch(true);
    try {
      const response = await api.delete<{ removed_count: number }>("/jobs/pool", {
        data: { job_ids: selectedJobPoolIds }
      });
      setSelectedJobPoolIds([]);
      await refreshWorkspace();
      await loadJobPool();
      setMessage({
        type: "success",
        text: `已移出 ${response.data.removed_count} 个岗位，岗位数据、AI 测评和面试历史已保留。`
      });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setRemovingJobPoolBatch(false);
    }
  }

  async function loadInterviewHistory() {
    if (!token) return;
    setInterviewHistoryLoading(true);
    try {
      const response = await api.get<InterviewHistoryItem[]>("/interviews/history");
      setInterviewHistory(response.data);
    } finally {
      setInterviewHistoryLoading(false);
    }
  }

  async function loadTaskStatuses() {
    if (!token) return;
    setTaskStatusesLoading(true);
    try {
      const response = await api.get<TaskStatusItem[]>("/tasks/status");
      setTaskStatuses(response.data);
    } finally {
      setTaskStatusesLoading(false);
    }
  }

  async function openInterviewDetail(sessionId: string) {
    setLoadingInterviewDetailId(sessionId);
    try {
      const response = await api.get<InterviewSession>(`/interviews/${sessionId}`);
      setActiveInterview(response.data);
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setLoadingInterviewDetailId(null);
    }
  }

  async function deleteInterviewHistory(sessionId: string) {
    const confirmed = window.confirm("确定删除这条面试历史吗？不会删除岗位、岗位池或 AI 测评。");
    if (!confirmed) return;
    setDeletingInterviewHistoryId(sessionId);
    try {
      await api.delete(`/interviews/history/${sessionId}`);
      setSelectedInterviewHistoryIds((previous) => previous.filter((id) => id !== sessionId));
      if (activeInterview?.id === sessionId) {
        setActiveInterview(null);
      }
      await loadInterviewHistory();
      await loadJobPool();
      setMessage({ type: "success", text: "面试历史已删除。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setDeletingInterviewHistoryId(null);
    }
  }

  async function deleteSelectedInterviewHistory() {
    if (selectedInterviewHistoryIds.length === 0) {
      setMessage({ type: "error", text: "请先选择要删除的面试历史。" });
      return;
    }
    const confirmed = window.confirm(
      `确定删除选中的 ${selectedInterviewHistoryIds.length} 条面试历史吗？不会删除岗位、岗位池或 AI 测评。`
    );
    if (!confirmed) return;
    const idsToDelete = [...selectedInterviewHistoryIds];
    setDeletingInterviewHistoryBatch(true);
    try {
      const response = await api.delete<{ deleted_count: number }>("/interviews/history", {
        data: { session_ids: idsToDelete }
      });
      setSelectedInterviewHistoryIds([]);
      if (activeInterview && idsToDelete.includes(activeInterview.id)) {
        setActiveInterview(null);
      }
      await loadInterviewHistory();
      await loadJobPool();
      setMessage({ type: "success", text: `已删除 ${response.data.deleted_count} 条面试历史。` });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setDeletingInterviewHistoryBatch(false);
    }
  }

  function toggleInterviewHistorySelection(sessionId: string, checked: boolean) {
    setSelectedInterviewHistoryIds((previous) => {
      if (checked) return previous.includes(sessionId) ? previous : [...previous, sessionId];
      return previous.filter((id) => id !== sessionId);
    });
  }

  function toggleInterviewHistoryPageSelection(checked: boolean) {
    setSelectedInterviewHistoryIds((previous) => {
      if (checked) return Array.from(new Set([...previous, ...interviewHistoryIds]));
      return previous.filter((id) => !interviewHistoryIds.includes(id));
    });
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
      setSelectedHistoryIds((previous) => previous.filter((id) => id !== sessionId));
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

  async function deleteSelectedHistorySessions() {
    if (selectedHistoryIds.length === 0) {
      setMessage({ type: "error", text: "请先选择要删除的搜索历史。" });
      return;
    }
    const confirmed = window.confirm(
      `确定删除选中的 ${selectedHistoryIds.length} 条搜索历史吗？岗位数据和已有 AI 测评不会被删除。`
    );
    if (!confirmed) return;

    const idsToDelete = [...selectedHistoryIds];
    setDeletingHistoryBatch(true);
    try {
      const response = await api.delete<{ deleted_count: number }>("/job-collections/sessions", {
        data: { session_ids: idsToDelete }
      });
      setHistoryDetails((previous) => {
        const next = { ...previous };
        idsToDelete.forEach((id) => {
          delete next[id];
        });
        return next;
      });
      setSelectedHistoryIds((previous) => previous.filter((id) => !idsToDelete.includes(id)));
      if (expandedHistoryId && idsToDelete.includes(expandedHistoryId)) {
        setExpandedHistoryId(null);
      }

      const nextTotal = Math.max((historyData?.total ?? idsToDelete.length) - response.data.deleted_count, 0);
      const nextPage = Math.min(historyPage, Math.max(Math.ceil(nextTotal / 10), 1));
      setHistoryPage(nextPage);
      await loadCollectionHistory(nextPage);
      setMessage({
        type: "success",
        text: `已删除 ${response.data.deleted_count} 条搜索历史，岗位数据和 AI 测评已保留。`
      });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setDeletingHistoryBatch(false);
    }
  }

  function toggleHistorySelection(sessionId: string, checked: boolean) {
    setSelectedHistoryIds((previous) => {
      if (checked) return previous.includes(sessionId) ? previous : [...previous, sessionId];
      return previous.filter((id) => id !== sessionId);
    });
  }

  function toggleHistoryPageSelection(checked: boolean) {
    setSelectedHistoryIds((previous) => {
      if (checked) return Array.from(new Set([...previous, ...historyPageIds]));
      return previous.filter((id) => !historyPageIds.includes(id));
    });
  }

  function toggleJobPoolSelection(jobId: string, checked: boolean) {
    setSelectedJobPoolIds((previous) => {
      if (checked) return previous.includes(jobId) ? previous : [...previous, jobId];
      return previous.filter((id) => id !== jobId);
    });
  }

  function toggleJobPoolPageSelection(checked: boolean) {
    setSelectedJobPoolIds((previous) => {
      if (checked) return Array.from(new Set([...previous, ...filteredJobPoolIds]));
      return previous.filter((id) => !filteredJobPoolIds.includes(id));
    });
  }

  function syncJob(updatedJob: Job) {
    setJobs((previous) => previous.map((job) => (job.id === updatedJob.id ? updatedJob : job)));
    setJobPool((previous) => {
      const withoutUpdated = previous.filter((job) => job.id !== updatedJob.id);
      return updatedJob.is_in_pool ? [updatedJob, ...withoutUpdated] : withoutUpdated;
    });
    setCollectionSession((previous) =>
      previous
        ? {
            ...previous,
            jobs: previous.jobs.map((job) => (job.id === updatedJob.id ? updatedJob : job))
          }
        : previous
    );
    setHistoryDetails((previous) => {
      const next: Record<string, JobCollectionSession> = {};
      for (const [sessionId, session] of Object.entries(previous)) {
        next[sessionId] = {
          ...session,
          jobs: session.jobs.map((job) => (job.id === updatedJob.id ? updatedJob : job))
        };
      }
      return next;
    });
  }

  async function addJobToPool(jobId: string) {
    setAddingToPoolJobId(jobId);
    try {
      const response = await api.post<Job>(`/jobs/${jobId}/pool`);
      syncJob(response.data);
      setMessage({ type: "success", text: "已确认投递，岗位已加入岗位池。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setAddingToPoolJobId(null);
    }
  }

  async function updateJobPoolItem(job: Job, patch: JobPoolItemPatch) {
    setSavingJobPoolItemId(job.id);
    try {
      const payload = {
        application_status: patch.application_status ?? job.application_status,
        applied_at: patch.applied_at === undefined ? job.applied_at ?? null : patch.applied_at,
        application_resume_version_id:
          patch.application_resume_version_id === undefined
            ? job.application_resume_version_id ?? getEffectiveResumeVersion(job.id)?.id ?? null
            : patch.application_resume_version_id,
        contact_name: job.contact_name ?? null,
        notes: patch.notes === undefined ? job.notes ?? null : patch.notes
      };
      const response = await api.patch<Job>(`/jobs/${job.id}/pool`, payload);
      syncJob(response.data);
      setMessage({ type: "success", text: "岗位池信息已保存。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setSavingJobPoolItemId(null);
    }
  }

  async function loadLatestEvaluations(jobList: Job[]) {
    const results = await Promise.all(
      jobList.map(async (job) => {
        try {
          const response = await api.get<JobEvaluation[]>(`/jobs/${job.id}/evaluations`);
          return [job.id, response.data] as const;
        } catch {
          return [job.id, [] as JobEvaluation[]] as const;
        }
      })
    );
    setEvaluationHistoriesByJobId((previous) => {
      const next = { ...previous };
      for (const [jobId, evaluations] of results) {
        next[jobId] = evaluations;
      }
      return next;
    });
    setEvaluationsByJobId((previous) => {
      const next = { ...previous };
      for (const [jobId, evaluations] of results) {
        if (evaluations[0]) next[jobId] = evaluations[0];
        else delete next[jobId];
      }
      return next;
    });
  }

  async function evaluateJob(jobId: string) {
    setEvaluatingJobId(jobId);
    try {
      const response = await api.post<JobEvaluation>(`/jobs/${jobId}/evaluations`, {});
      setEvaluationsByJobId((previous) => ({ ...previous, [jobId]: response.data }));
      setEvaluationHistoriesByJobId((previous) => ({
        ...previous,
        [jobId]: [response.data, ...(previous[jobId] ?? [])]
      }));
      setMessage({
        type: "success",
        text: `AI 测评完成：${response.data.final_score.toFixed(1)}/100，使用${resumeSourceText(response.data.resume_source_type)}，建议：${response.data.recommendation}`
      });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setEvaluatingJobId(null);
    }
  }

  async function uploadJobResume() {
    if (!jobResumeModalJob) return;
    if (!jobResumeFile) {
      setJobResumeUploadError("请先选择 .docx、.md 或 .pdf 简历文件。");
      return;
    }
    setUploadingJobResumeId(jobResumeModalJob.id);
    setJobResumeUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", jobResumeFile);
      await api.post<ResumeVersion>(`/resumes/jobs/${jobResumeModalJob.id}/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setJobResumeModalJob(null);
      setJobResumeFile(null);
      setJobResumeUploadError(null);
      await refreshWorkspace();
      if (activeSection === "job_pool") {
        await loadJobPool();
      }
      setMessage({ type: "success", text: "岗位简历上传成功，后续 AI 测评会优先使用这份简历。" });
    } catch (error) {
      const text = errorMessage(error);
      setJobResumeUploadError(text);
      setMessage({ type: "error", text });
    } finally {
      setUploadingJobResumeId(null);
    }
  }

  function openJobResumeUpload(job: Job) {
    setJobResumeModalJob(job);
    setJobResumeFile(null);
    setJobResumeUploadError(null);
  }

  function getJobSpecificResumeVersions(jobId: string) {
    return allResumeVersions
      .filter((version) => version.job_id === jobId)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }

  function getEffectiveResumeVersion(jobId: string): ResumeVersion | undefined {
    return getJobSpecificResumeVersions(jobId)[0] ?? defaultResumeVersion;
  }

  function getEvaluationDelta(jobId: string) {
    const history = evaluationHistoriesByJobId[jobId] ?? [];
    if (history.length < 2) return null;
    const [latest, previous] = history;
    return {
      latest,
      previous,
      scoreDelta: latest.final_score - previous.final_score
    };
  }

  async function startInterview(jobId: string) {
    setInterviewLoadingJobId(jobId);
    try {
      const response = await api.post<InterviewSession>("/interviews", {
        job_id: jobId,
        max_questions: 5
      });
      setActiveInterview(response.data);
      interviewAnswerForm.resetFields();
      setActiveSection("interview");
      setMessage({ type: "success", text: "模拟面试已开始，请回答当前问题。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setInterviewLoadingJobId(null);
    }
  }

  async function submitInterviewAnswer(values: { answer_text: string }) {
    if (!activeInterview) return;
    setAnswerSubmitting(true);
    try {
      const response = await api.post<InterviewSession>(
        `/interviews/${activeInterview.id}/answers`,
        values
      );
      setActiveInterview(response.data);
      interviewAnswerForm.resetFields();
      await loadInterviewHistory();
      await loadJobPool();
      setMessage({
        type: "success",
        text: response.data.status === "completed" ? "模拟面试已完成，报告已生成。" : "回答已提交，进入下一步。"
      });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setAnswerSubmitting(false);
    }
  }

  async function finishInterview() {
    if (!activeInterview) return;
    setAnswerSubmitting(true);
    try {
      const response = await api.post<InterviewSession>(`/interviews/${activeInterview.id}/finish`);
      setActiveInterview(response.data);
      await loadInterviewHistory();
      await loadJobPool();
      setMessage({ type: "success", text: "已结束模拟面试并生成报告。" });
    } catch (error) {
      setMessage({ type: "error", text: errorMessage(error) });
    } finally {
      setAnswerSubmitting(false);
    }
  }

  function renderJobResumeVersionPanel(job: Job) {
    const jobVersions = getJobSpecificResumeVersions(job.id);
    const effectiveVersion = getEffectiveResumeVersion(job.id);
    const latestJobVersion = jobVersions[0];
    const delta = getEvaluationDelta(job.id);

    return (
      <div className="resume-version-panel">
        <div className="resume-version-header">
          <div>
            <Text strong>测评简历</Text>
            <Text type="secondary">
              {latestJobVersion
                ? "已上传岗位简历，AI 测评会优先使用这份简历。"
                : "未上传岗位简历，AI 测评会使用基础配置里的默认简历。"}
            </Text>
          </div>
          <Tag color={latestJobVersion ? "blue" : "default"}>
            {latestJobVersion ? "岗位上传优先" : "使用默认简历"}
          </Tag>
        </div>
        <Space wrap className="resume-version-actions">
          <Button
            icon={<UploadCloud size={16} />}
            onClick={() => openJobResumeUpload(job)}
          >
            {latestJobVersion ? "更换简历" : "上传简历"}
          </Button>
          <Button
            type="primary"
            disabled={!effectiveVersion}
            loading={evaluatingJobId === job.id}
            onClick={() => evaluateJob(job.id)}
          >
            {latestJobVersion ? "用岗位简历复评" : "AI 测评"}
          </Button>
          {delta && (
            <Tag color={delta.scoreDelta >= 0 ? "green" : "red"}>
              较上次 {delta.scoreDelta >= 0 ? "+" : ""}
              {delta.scoreDelta.toFixed(1)} 分
            </Tag>
          )}
        </Space>
        <Text type="secondary">
          当前：{effectiveVersion ? `${resumeSourceText(effectiveVersion.source_type)} · ${effectiveVersion.title}` : "暂无可用简历"}
          {latestJobVersion ? ` · 上传于 ${formatDateTime(latestJobVersion.created_at)}` : ""}
        </Text>
      </div>
    );
  }

  function renderJobPoolInfoPanel(job: Job) {
    const saving = savingJobPoolItemId === job.id;
    const selectedResumeVersionId =
      job.application_resume_version_id ?? getEffectiveResumeVersion(job.id)?.id;

    return (
      <div className="job-pool-meta" key={`${job.id}-${job.status_changed_at ?? "new"}`}>
        <div className="job-pool-meta-header">
          <div>
            <Text strong>投递跟进</Text>
            <Text type="secondary">保存岗位状态、投递时间、备注和本次使用的简历版本。</Text>
          </div>
          {job.status_changed_at && (
            <Text type="secondary">更新：{formatDateTime(job.status_changed_at)}</Text>
          )}
        </div>
        <div className="job-pool-meta-grid">
          <label>
            <Text type="secondary">状态</Text>
            <Select
              disabled={saving}
              value={job.application_status}
              options={APPLICATION_STATUS_OPTIONS}
              onChange={(value) => updateJobPoolItem(job, { application_status: value })}
            />
          </label>
          <label>
            <Text type="secondary">投递时间</Text>
            <Input
              type="date"
              disabled={saving}
              defaultValue={dateInputValue(job.applied_at)}
              onBlur={(event) => {
                const next = event.target.value || null;
                if (next !== dateInputValue(job.applied_at)) {
                  updateJobPoolItem(job, { applied_at: next });
                }
              }}
            />
          </label>
          <label>
            <Text type="secondary">使用简历</Text>
            <Select
              allowClear
              disabled={saving || allResumeVersions.length === 0}
              placeholder="选择测评/投递简历"
              value={selectedResumeVersionId}
              options={allResumeVersions.map((version) => ({
                value: version.id,
                label: `${resumeSourceText(version.source_type)} · ${version.title}`
              }))}
              onChange={(value) =>
                updateJobPoolItem(job, { application_resume_version_id: value ?? null })
              }
            />
          </label>
        </div>
        <label className="job-pool-notes">
          <Text type="secondary">备注</Text>
          <Input.TextArea
            disabled={saving}
            defaultValue={job.notes ?? ""}
            placeholder="记录投递渠道、沟通重点、复盘结论等"
            autoSize={{ minRows: 2, maxRows: 4 }}
            onBlur={(event) => {
              const next = event.target.value.trim() || null;
              if (next !== (job.notes ?? null)) {
                updateJobPoolItem(job, { notes: next });
              }
            }}
          />
        </label>
      </div>
    );
  }

  function renderJobList(jobList: Job[], emptyText: string, readonly = false) {
    return (
      <List
        dataSource={jobList}
        locale={{ emptyText }}
        renderItem={(item) => {
          const evaluation = evaluationsByJobId[item.id];
          return (
            <List.Item
              actions={
                readonly
                  ? []
                  : [
                      <Button
                        key="evaluate"
                        type={evaluation ? "default" : "primary"}
                        loading={evaluatingJobId === item.id}
                        onClick={() => evaluateJob(item.id)}
                      >
                        {evaluation ? "重新 AI 测评" : "AI 测评"}
                      </Button>,
                      <Button
                        key="pool"
                        disabled={item.is_in_pool}
                        loading={addingToPoolJobId === item.id}
                        onClick={() => addJobToPool(item.id)}
                      >
                        {item.is_in_pool ? "已确认投递" : "确认投递"}
                      </Button>
                    ]
              }
            >
              <List.Item.Meta
                title={
                  <Space wrap>
                    <a href={item.job_url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                    {item.is_in_pool && <Tag color="green">已入岗位池</Tag>}
                    {item.has_interviewed && <Tag color="purple">已模拟面试</Tag>}
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
    setJobPool([]);
    setJobPoolFilter("");
    setJobPoolStatusFilter(undefined);
    setJobPoolCompanyFilter("");
    setJobPoolCityFilter("");
    setSelectedJobPoolIds([]);
    setActiveInterview(null);
    setInterviewHistory([]);
    setSelectedInterviewHistoryIds([]);
    setProfileDirty(false);
    setProviderDirty(false);
    setSelectedHistoryIds([]);
    setHistoryDetails({});
    setHistoryData(null);
  }

  return (
    <ConfigProvider theme={{ token: { colorPrimary: "#1677ff", borderRadius: 8 } }}>
      <Layout className="app-shell">
        <Header className="app-header">
          <Space>
            <Bot size={22} />
            <Text className="brand">ai-job-AGENT</Text>
            <Tag color="blue">V0.1 本地闭环</Tag>
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
          <Modal
            title={jobResumeModalJob ? `上传简历：${jobResumeModalJob.title}` : "上传岗位简历"}
            open={Boolean(jobResumeModalJob)}
            onCancel={() => {
              setJobResumeModalJob(null);
              setJobResumeFile(null);
              setJobResumeUploadError(null);
            }}
            footer={[
              <Button
                key="cancel"
                onClick={() => {
                  setJobResumeModalJob(null);
                  setJobResumeFile(null);
                  setJobResumeUploadError(null);
                }}
              >
                取消
              </Button>,
              <Button
                key="upload"
                type="primary"
                loading={Boolean(jobResumeModalJob && uploadingJobResumeId === jobResumeModalJob.id)}
                disabled={!jobResumeFile}
                onClick={uploadJobResume}
              >
                上传并解析
              </Button>
            ]}
            destroyOnHidden
          >
            <Space direction="vertical" size={12} className="job-resume-upload-modal">
              <Text type="secondary">
                上传你在 WPS 或 Word 中改好的简历。该岗位后续 AI 测评会优先使用这份简历，不会覆盖基础配置里的默认简历。
              </Text>
              {jobResumeUploadError && (
                <Alert type="error" showIcon message={jobResumeUploadError} />
              )}
              <Upload.Dragger
                accept=".docx,.md,.pdf"
                maxCount={1}
                disabled={Boolean(jobResumeModalJob && uploadingJobResumeId === jobResumeModalJob.id)}
                beforeUpload={(file) => {
                  setJobResumeFile(file);
                  setJobResumeUploadError(null);
                  return false;
                }}
                onRemove={() => setJobResumeFile(null)}
              >
                <p className="upload-title">点击或拖拽上传岗位简历</p>
                <p className="upload-desc">支持 .docx、.md、文本型 .pdf；扫描版 PDF 暂不支持 OCR。</p>
              </Upload.Dragger>
              {jobResumeFile && (
                <Text type="secondary">
                  已选择：{jobResumeFile.name}（{(jobResumeFile.size / 1024).toFixed(1)} KB）
                </Text>
              )}
            </Space>
          </Modal>

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
                <button
                  className={`sidebar-item ${activeSection === "job_pool" ? "active" : ""}`}
                  onClick={() => setActiveSection("job_pool")}
                >
                  <BriefcaseBusiness size={18} />
                  <span>岗位池</span>
                </button>
                <button
                  className={`sidebar-item ${activeSection === "interview" ? "active" : ""}`}
                  onClick={() => setActiveSection("interview")}
                >
                  <MessageSquareText size={18} />
                  <span>模拟面试</span>
                </button>
                <button
                  className={`sidebar-item ${activeSection === "interview_history" ? "active" : ""}`}
                  onClick={() => setActiveSection("interview_history")}
                >
                  <History size={18} />
                  <span>面试历史</span>
                </button>
                <button
                  className={`sidebar-item ${activeSection === "tasks" ? "active" : ""}`}
                  onClick={() => setActiveSection("tasks")}
                >
                  <ShieldCheck size={18} />
                  <span>任务状态</span>
                </button>
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
                <Form
                  form={profileForm}
                  layout="vertical"
                  onFinish={saveProfile}
                  onValuesChange={() => setProfileDirty(true)}
                >
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
                  <Button type={profileDirty ? "primary" : "default"} htmlType="submit" disabled={!profileDirty}>
                    {profileDirty ? "保存个人配置" : "个人配置已保存，修改后可再次保存"}
                  </Button>
                </Form>
              </Card>

              <Card className="config-section" title={<CardTitle icon={<ShieldCheck size={18} />} text="AI 模型配置" />}>
                <Form
                  form={providerForm}
                  layout="vertical"
                  onFinish={saveProvider}
                  onValuesChange={() => setProviderDirty(true)}
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
                  <Button type={providerDirty ? "primary" : "default"} htmlType="submit" disabled={!providerDirty}>
                    {providerDirty
                      ? "保存 AI 配置"
                      : providers.length > 0
                        ? "AI 配置已保存，修改后可再次保存"
                        : "填写后保存 AI 配置"}
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
                        </Button>,
                        <Button
                          key="delete"
                          danger
                          loading={deletingProviderId === item.id}
                          onClick={() => deleteProvider(item.id)}
                        >
                          删除
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
                  dataSource={baseResumeFiles}
                  locale={{ emptyText: "暂无简历" }}
                  renderItem={(item) => (
                    <List.Item
                      actions={[
                        !item.is_default && (
                          <Button
                            key="default"
                            loading={settingDefaultResumeId === item.id}
                            onClick={() => setDefaultResume(item.id)}
                          >
                            设为默认
                          </Button>
                        ),
                        <Button
                          key="delete"
                          danger
                          loading={deletingResumeId === item.id}
                          onClick={() => deleteResume(item.id)}
                        >
                          删除
                        </Button>
                      ].filter(Boolean)}
                    >
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
                        setEvaluationHistoriesByJobId({});
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
                    type={collectionStatusAlertType(collectionSession.status)}
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
                <div className="history-toolbar">
                  <Space wrap>
                    <Checkbox
                      checked={isHistoryPageFullySelected}
                      indeterminate={isHistoryPagePartiallySelected}
                      disabled={historyPageIds.length === 0}
                      onChange={(event) => toggleHistoryPageSelection(event.target.checked)}
                    >
                      选择本页
                    </Checkbox>
                    <Button
                      danger
                      disabled={selectedHistoryIds.length === 0}
                      loading={deletingHistoryBatch}
                      onClick={deleteSelectedHistorySessions}
                    >
                      批量删除{selectedHistoryIds.length > 0 ? `（${selectedHistoryIds.length}）` : ""}
                    </Button>
                  </Space>
                  <Text type="secondary">删除历史只移除搜索记录，不会删除岗位、岗位池和 AI 测评。</Text>
                </div>
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
                                <Checkbox
                                  checked={selectedHistoryIds.includes(item.id)}
                                  onChange={(event) => toggleHistorySelection(item.id, event.target.checked)}
                                />
                                <Text strong>{item.keyword}</Text>
                                {item.city && <Tag>{item.city}</Tag>}
                                {item.work_type && <Tag>{workTypeText(item.work_type)}</Tag>}
                                <Tag color={collectionStatusColor(item.status)}>
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
                                ? renderJobList(detail.jobs, "这次搜索没有可展示岗位。", true)
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

              <Card
                className="wide-card pool-section"
                title={<CardTitle icon={<BriefcaseBusiness size={18} />} text="岗位池" />}
                extra={<Button onClick={() => loadJobPool()} loading={jobPoolLoading}>刷新岗位池</Button>}
              >
                <Alert
                  className="pool-guide"
                  type="info"
                  showIcon
                  message="岗位池用于保存你已确认准备投递的岗位"
                  description="这里会复用同一份岗位和 AI 测评记录；可以从岗位池直接开始岗位专属模拟面试。"
                />
                <div className="history-toolbar">
                  <Space wrap>
                    <Checkbox
                      checked={isJobPoolFullySelected}
                      indeterminate={isJobPoolPartiallySelected}
                      disabled={filteredJobPoolIds.length === 0}
                      onChange={(event) => toggleJobPoolPageSelection(event.target.checked)}
                    >
                      选择当前列表
                    </Checkbox>
                    <Button
                      danger
                      icon={<Trash2 size={16} />}
                      disabled={selectedJobPoolIds.length === 0}
                      loading={removingJobPoolBatch}
                      onClick={removeSelectedJobsFromPool}
                    >
                      批量移出{selectedJobPoolIds.length > 0 ? `（${selectedJobPoolIds.length}）` : ""}
                    </Button>
                  </Space>
                  <Text type="secondary">只移出岗位池，不删除岗位、AI 测评和面试历史。</Text>
                </div>
                <Space wrap className="pool-filter">
                  <Select
                    allowClear
                    className="pool-status-filter"
                    placeholder="岗位状态"
                    value={jobPoolStatusFilter}
                    options={APPLICATION_STATUS_OPTIONS}
                    onChange={(value) => setJobPoolStatusFilter(value)}
                  />
                  <Input
                    allowClear
                    className="pool-small-filter"
                    placeholder="公司"
                    value={jobPoolCompanyFilter}
                    onChange={(event) => setJobPoolCompanyFilter(event.target.value)}
                  />
                  <Input
                    allowClear
                    className="pool-small-filter"
                    placeholder="城市"
                    value={jobPoolCityFilter}
                    onChange={(event) => setJobPoolCityFilter(event.target.value)}
                  />
                  <Input.Search
                    allowClear
                    className="pool-keyword-filter"
                    placeholder="岗位名 / 标签 / JD"
                    value={jobPoolFilter}
                    onChange={(event) => setJobPoolFilter(event.target.value)}
                    onSearch={() => loadJobPool()}
                  />
                  <Button
                    onClick={() => {
                      setJobPoolStatusFilter(undefined);
                      setJobPoolCompanyFilter("");
                      setJobPoolCityFilter("");
                      setJobPoolFilter("");
                    }}
                  >
                    清空筛选
                  </Button>
                </Space>
                <List
                  loading={jobPoolLoading}
                  dataSource={filteredJobPool}
                  locale={{
                    emptyText: jobPoolFilter
                      ? "没有匹配当前筛选条件的岗位。"
                      : "暂无岗位池记录。请先在搜索结果或历史记录中点击“确认投递”。"
                  }}
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
                          <Button
                            key="interview"
                            loading={interviewLoadingJobId === item.id}
                            onClick={() => startInterview(item.id)}
                          >
                            开始模拟面试
                          </Button>
                        ]}
                      >
                        <List.Item.Meta
                          title={
                            <Space wrap>
                              <Checkbox
                                checked={selectedJobPoolIds.includes(item.id)}
                                onChange={(event) => toggleJobPoolSelection(item.id, event.target.checked)}
                              />
                              <a href={item.job_url} target="_blank" rel="noreferrer">
                                {item.title}
                              </a>
                              <Tag color={applicationStatusColor(item.application_status)}>
                                {applicationStatusText(item.application_status)}
                              </Tag>
                              {item.has_interviewed && <Tag color="purple">已模拟面试</Tag>}
                              {evaluation && (
                                <Tag color={evaluationTagColor(evaluation.final_score)}>
                                  {evaluation.recommendation}
                                </Tag>
                              )}
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
                              {renderJobPoolInfoPanel(item)}
                              {renderJobResumeVersionPanel(item)}
                              {evaluation && (
                                <EvaluationSummary evaluation={evaluation} delta={getEvaluationDelta(item.id)} />
                              )}
                            </Space>
                          }
                        />
                      </List.Item>
                    );
                  }}
                />
              </Card>

              <Card
                className="wide-card current-interview-section"
                title={<CardTitle icon={<MessageSquareText size={18} />} text="模拟面试" />}
                extra={
                  activeInterview?.status === "running" &&
                  activeInterview.turns.some((turn) => turn.status === "answered") ? (
                    <Button onClick={finishInterview} loading={answerSubmitting}>
                      结束并生成报告
                    </Button>
                  ) : null
                }
              >
                {!activeInterview ? (
                  <Alert
                    type="info"
                    showIcon
                    message="请从岗位池选择一个岗位开始模拟面试"
                    description="当前版本使用本地题库检索和规则评分；已完成的记录请到左侧“面试历史”查看。"
                  />
                ) : (
                  <Space direction="vertical" size={16} className="interview-stack">
                    <div className="interview-header">
                      <div>
                        <Text strong>{activeInterview.job_title}</Text>
                        <Text type="secondary"> / {activeInterview.company}</Text>
                      </div>
                      <Space wrap>
                        <Tag color={activeInterview.status === "completed" ? "green" : "blue"}>
                          {activeInterview.status === "completed" ? "已完成" : "进行中"}
                        </Tag>
                        <Tag>
                          主问题 {activeInterview.main_questions_answered}/{activeInterview.max_questions}
                        </Tag>
                        <Tag>{activeInterview.retrieval_mode}</Tag>
                        <Tag>{activeInterview.checkpoint.mode}</Tag>
                      </Space>
                    </div>

                    {activeInterview.current_turn && activeInterview.status === "running" && (
                      <div className="current-question">
                        <Space wrap className="question-tags">
                          <Tag color={activeInterview.current_turn.is_followup ? "orange" : "purple"}>
                            {activeInterview.current_turn.is_followup ? "追问" : "主问题"}
                          </Tag>
                          {activeInterview.current_turn.skill_tags.map((tag) => (
                            <Tag key={tag}>{tag}</Tag>
                          ))}
                        </Space>
                        <Title level={4}>{activeInterview.current_turn.question_text}</Title>
                        <Form form={interviewAnswerForm} layout="vertical" onFinish={submitInterviewAnswer}>
                          <Form.Item name="answer_text" rules={[{ required: true, message: "请输入你的回答" }]}>
                            <Input.TextArea rows={6} placeholder="写下你的回答，尽量包含项目证据、实现步骤和边界说明。" />
                          </Form.Item>
                          <Button type="primary" htmlType="submit" loading={answerSubmitting}>
                            提交回答
                          </Button>
                        </Form>
                      </div>
                    )}

                    <List
                      className="turn-list"
                      dataSource={activeInterview.turns.filter((turn) => turn.status === "answered")}
                      locale={{ emptyText: "还没有已完成的回答。" }}
                      renderItem={(turn) => (
                        <List.Item>
                          <List.Item.Meta
                            title={
                              <Space wrap>
                                <Text strong>
                                  第 {turn.turn_index} 轮 · {turn.is_followup ? "追问" : "问题"}
                                </Text>
                                {typeof turn.score === "number" && (
                                  <Tag color={evaluationTagColor(turn.score)}>{turn.score.toFixed(1)} 分</Tag>
                                )}
                              </Space>
                            }
                            description={
                              <Space direction="vertical" size={8} className="job-meta-stack">
                                <Text>{turn.question_text}</Text>
                                <Text type="secondary">回答：{turn.answer_text}</Text>
                                {turn.feedback && <Text>{turn.feedback}</Text>}
                                {turn.evidence.length > 0 && (
                                  <ul className="compact-list">
                                    {turn.evidence.map((item) => (
                                      <li key={item}>{item}</li>
                                    ))}
                                  </ul>
                                )}
                              </Space>
                            }
                          />
                        </List.Item>
                      )}
                    />

                    {activeInterview.report && Number(activeInterview.report.question_count ?? 0) > 0 && (
                      <div className="interview-report">
                        <div className="evaluation-header">
                          <div>
                            <Text strong>
                              面试报告 {Number(activeInterview.report.total_score ?? 0).toFixed(1)}/100
                            </Text>
                            <Text type="secondary"> · {activeInterview.report.summary}</Text>
                          </div>
                          <Tag color={evaluationTagColor(Number(activeInterview.report.total_score ?? 0))}>
                            {activeInterview.report.question_count ?? 0} 轮回答
                          </Tag>
                        </div>
                        {Boolean(activeInterview.report.covered_skills?.length) && (
                          <Space wrap className="evaluation-dimensions">
                            {activeInterview.report.covered_skills?.map((skill) => (
                              <Tag key={skill}>{skill}</Tag>
                            ))}
                          </Space>
                        )}
                        <ReportList title="优势" items={activeInterview.report.strengths ?? []} />
                        <ReportList title="缺口" items={activeInterview.report.gaps ?? []} />
                        <ReportList title="复习建议" items={activeInterview.report.review_suggestions ?? []} />
                        <ReportSections report={activeInterview.report} />
                      </div>
                    )}
                  </Space>
                )}
              </Card>


              <Card
                className="wide-card interview-history-section"
                title={<CardTitle icon={<History size={18} />} text="面试历史" />}
                extra={<Button onClick={() => loadInterviewHistory()} loading={interviewHistoryLoading}>刷新历史</Button>}
              >
                <div className="history-toolbar">
                  <Space wrap>
                    <Checkbox
                      checked={isInterviewHistoryFullySelected}
                      indeterminate={isInterviewHistoryPartiallySelected}
                      disabled={interviewHistoryIds.length === 0}
                      onChange={(event) => toggleInterviewHistoryPageSelection(event.target.checked)}
                    >
                      选择全部
                    </Checkbox>
                    <Button
                      danger
                      icon={<Trash2 size={16} />}
                      disabled={selectedInterviewHistoryIds.length === 0}
                      loading={deletingInterviewHistoryBatch}
                      onClick={deleteSelectedInterviewHistory}
                    >
                      批量删除{selectedInterviewHistoryIds.length > 0 ? `（${selectedInterviewHistoryIds.length}）` : ""}
                    </Button>
                    <Button onClick={() => setActiveSection("job_pool")}>新增面试</Button>
                  </Space>
                  <Text type="secondary">删除面试历史不会删除岗位、岗位池或 AI 测评。</Text>
                </div>
                <List
                  className="interview-history-list"
                  loading={interviewHistoryLoading}
                  dataSource={interviewHistory}
                  locale={{ emptyText: "暂无面试历史。请从岗位池开始一次模拟面试并至少提交一轮回答。" }}
                  renderItem={(item) => (
                    <List.Item
                      actions={[
                        <Button
                          key="detail"
                          loading={loadingInterviewDetailId === item.id}
                          onClick={() => openInterviewDetail(item.id)}
                        >
                          查看详情
                        </Button>,
                        <Button
                          key="delete"
                          danger
                          loading={deletingInterviewHistoryId === item.id}
                          onClick={() => deleteInterviewHistory(item.id)}
                        >
                          删除记录
                        </Button>
                      ]}
                    >
                      <List.Item.Meta
                        title={
                          <Space wrap>
                            <Checkbox
                              checked={selectedInterviewHistoryIds.includes(item.id)}
                              onChange={(event) => toggleInterviewHistorySelection(item.id, event.target.checked)}
                            />
                            <Text strong>{item.job_title}</Text>
                            <Text type="secondary">/ {item.company}</Text>
                            <Tag color={item.status === "completed" ? "green" : "blue"}>
                              {item.status === "completed" ? "已完成" : "进行中"}
                            </Tag>
                            {typeof item.total_score === "number" && (
                              <Tag color={evaluationTagColor(item.total_score)}>
                                {item.total_score.toFixed(1)} 分
                              </Tag>
                            )}
                          </Space>
                        }
                        description={
                          <Space direction="vertical" size={4}>
                            <Text type="secondary">
                              {item.location ? `${item.location} · ` : ""}
                              {item.salary ? `${item.salary} · ` : ""}
                              面试时间：{formatDateTime(item.created_at)}
                              {item.completed_at ? ` · 完成：${formatDateTime(item.completed_at)}` : ""}
                            </Text>
                            <Text type="secondary">
                              已答 {item.question_count} 轮，主问题 {item.main_questions_answered} 轮
                            </Text>
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
                {activeInterview ? (
                  <>
                    <Divider />
                    <Space direction="vertical" size={16} className="interview-stack">
                      <div className="interview-header">
                        <div>
                          <Text strong>{activeInterview.job_title}</Text>
                          <Text type="secondary"> / {activeInterview.company}</Text>
                        </div>
                        <Space wrap>
                          <Tag color={activeInterview.status === "completed" ? "green" : "blue"}>
                            {activeInterview.status === "completed" ? "已完成" : "进行中"}
                          </Tag>
                          <Tag>
                            主问题 {activeInterview.main_questions_answered}/{activeInterview.max_questions}
                          </Tag>
                          <Tag>{activeInterview.retrieval_mode}</Tag>
                          <Tag>{activeInterview.checkpoint.mode}</Tag>
                        </Space>
                      </div>
                      <List
                        className="turn-list"
                        dataSource={activeInterview.turns.filter((turn) => turn.status === "answered")}
                        locale={{ emptyText: "这条面试还没有已完成的回答。" }}
                        renderItem={(turn) => (
                          <List.Item>
                            <List.Item.Meta
                              title={
                                <Space wrap>
                                  <Text strong>
                                    第 {turn.turn_index} 轮 · {turn.is_followup ? "追问" : "问题"}
                                  </Text>
                                  {typeof turn.score === "number" && (
                                    <Tag color={evaluationTagColor(turn.score)}>{turn.score.toFixed(1)} 分</Tag>
                                  )}
                                </Space>
                              }
                              description={
                                <Space direction="vertical" size={8} className="job-meta-stack">
                                  <Text>{turn.question_text}</Text>
                                  <Text type="secondary">回答：{turn.answer_text}</Text>
                                  {turn.feedback && <Text>{turn.feedback}</Text>}
                                  {turn.evidence.length > 0 && (
                                    <ul className="compact-list">
                                      {turn.evidence.map((item) => (
                                        <li key={item}>{item}</li>
                                      ))}
                                    </ul>
                                  )}
                                </Space>
                              }
                            />
                          </List.Item>
                        )}
                      />
                      {activeInterview.report && Number(activeInterview.report.question_count ?? 0) > 0 && (
                        <div className="interview-report">
                          <div className="evaluation-header">
                            <div>
                              <Text strong>
                                面试报告 {Number(activeInterview.report.total_score ?? 0).toFixed(1)}/100
                              </Text>
                              <Text type="secondary"> · {activeInterview.report.summary}</Text>
                            </div>
                            <Tag color={evaluationTagColor(Number(activeInterview.report.total_score ?? 0))}>
                              {activeInterview.report.question_count ?? 0} 轮回答
                            </Tag>
                          </div>
                          {Boolean(activeInterview.report.covered_skills?.length) && (
                            <Space wrap className="evaluation-dimensions">
                              {activeInterview.report.covered_skills?.map((skill) => (
                                <Tag key={skill}>{skill}</Tag>
                              ))}
                            </Space>
                          )}
                          <ReportList title="优势" items={activeInterview.report.strengths ?? []} />
                          <ReportList title="缺口" items={activeInterview.report.gaps ?? []} />
                          <ReportList title="复习建议" items={activeInterview.report.review_suggestions ?? []} />
                          <ReportSections report={activeInterview.report} />
                        </div>
                      )}
                    </Space>
                  </>
                ) : null}
              </Card>


              <Card
                className="wide-card tasks-section"
                title={<CardTitle icon={<ShieldCheck size={18} />} text="任务状态" />}
                extra={<Button onClick={() => loadTaskStatuses()} loading={taskStatusesLoading}>刷新状态</Button>}
              >
                <List
                  loading={taskStatusesLoading}
                  dataSource={taskStatuses}
                  locale={{ emptyText: "暂无任务状态。" }}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta
                        title={
                          <Space wrap>
                            <Text strong>{item.name}</Text>
                            <Tag color={taskStatusColor(item.status)}>{taskStatusText(item.status)}</Tag>
                            <Tag>{item.backend}</Tag>
                          </Space>
                        }
                        description={
                          <Space direction="vertical" size={4}>
                            <Text>{item.detail}</Text>
                            {item.updated_at && <Text type="secondary">更新时间：{formatDateTime(item.updated_at)}</Text>}
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
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

function EvaluationSummary({
  evaluation,
  delta
}: {
  evaluation: JobEvaluation;
  delta?: { previous: JobEvaluation; scoreDelta: number } | null;
}) {
  const dimensions = Object.entries(evaluation.dimensions);
  const requirements = evaluation.jd_requirements;
  const requiredSkills = requirements?.required_skills ?? [];
  const preferredSkills = requirements?.preferred_skills ?? [];
  const hasRequirements = requiredSkills.length > 0 || preferredSkills.length > 0;
  const recommendationChanged =
    Boolean(delta) && delta?.previous.recommendation !== evaluation.recommendation;
  return (
    <div className="evaluation-panel">
      <div className="evaluation-header">
        <div>
          <Text strong>匹配度 {evaluation.final_score.toFixed(1)}/100</Text>
          <Text type="secondary"> · {evaluation.one_sentence_reason}</Text>
        </div>
        <Space wrap>
          {delta && (
            <Tag color={delta.scoreDelta >= 0 ? "green" : "red"}>
              较上次 {delta.scoreDelta >= 0 ? "+" : ""}
              {delta.scoreDelta.toFixed(1)} 分
            </Tag>
          )}
          {recommendationChanged && delta && (
            <Tag color="purple">
              {delta.previous.recommendation} → {evaluation.recommendation}
            </Tag>
          )}
          <Tag color={evaluationTagColor(evaluation.final_score)}>{evaluation.recommendation}</Tag>
        </Space>
      </div>
      <Space wrap size={[6, 6]} className="evaluation-dimensions">
        {dimensions.map(([key, dimension]) => {
          const previousDimension = delta?.previous.dimensions[key];
          const dimensionDelta =
            previousDimension !== undefined ? dimension.score - previousDimension.score : null;
          return (
            <Tag key={key}>
              {evaluationDimensionName(key)} {dimension.score.toFixed(0)}
              {dimensionDelta !== null && (
                <>
                  {" "}
                  {dimensionDelta >= 0 ? "+" : ""}
                  {dimensionDelta.toFixed(0)}
                </>
              )}
              {dimension.data_status === "insufficient_data" ? "（信息不足）" : ""}
            </Tag>
          );
        })}
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
        框架 {evaluation.framework_version}，输出 {evaluation.output_schema_version}，测评简历：
        {resumeSourceText(evaluation.resume_source_type)} · 版本：
        {evaluation.resume_title ?? evaluation.resume_version_id}
      </Text>
    </div>
  );
}

function ReportList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="evaluation-block">
      <Text strong>{title}：</Text>
      <ul className="compact-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

interface InterviewReport {
  total_score?: number;
  question_count?: number;
  summary?: string;
  strengths?: string[];
  gaps?: string[];
  review_suggestions?: string[];
  covered_skills?: string[];
  skill_dimensions?: { skill: string; score: number; question_count: number }[];
  fact_based_analysis?: string[];
  inference_notes?: string[];
  previous_reports?: {
    session_id: string;
    completed_at?: string | null;
    total_score: number;
    question_count: number;
  }[];
  evidence?: {
    question: string;
    answer?: string | null;
    score?: number | null;
    rubric_evidence?: string[];
    source_question_id?: string | null;
  }[];
}

function ReportSections({ report }: { report: InterviewReport }) {
  const dimensions = report.skill_dimensions ?? [];
  const facts = report.fact_based_analysis ?? [];
  const inferences = report.inference_notes ?? [];
  const history = report.previous_reports ?? [];
  const evidence = report.evidence ?? [];
  const currentScore = Number(report.total_score ?? 0);

  return (
    <>
      {dimensions.length > 0 && (
        <div className="evaluation-block">
          <Text strong>技能维度：</Text>
          <Space wrap className="evaluation-dimensions">
            {dimensions.map((dimension) => (
              <Tag key={dimension.skill} color={evaluationTagColor(dimension.score)}>
                {dimension.skill} {dimension.score.toFixed(1)} 分（{dimension.question_count} 题）
              </Tag>
            ))}
          </Space>
        </div>
      )}
      {facts.length > 0 && (
        <div className="evaluation-block">
          <Text strong>事实依据：</Text>
          <ul className="compact-list">
            {facts.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {inferences.length > 0 && (
        <div className="evaluation-block">
          <Text strong>推测性评价：</Text>
          <ul className="compact-list">
            {inferences.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {history.length > 0 && (
        <div className="evaluation-block">
          <Text strong>历史对比（同岗位最近 {history.length} 次）：</Text>
          <ul className="compact-list">
            {history.map((item) => {
              const delta = currentScore - item.total_score;
              return (
                <li key={item.session_id}>
                  {item.completed_at ? new Date(item.completed_at).toLocaleString() : "完成时间未知"}：
                  {item.total_score.toFixed(1)} 分 / {item.question_count} 题
                  <Tag color={delta >= 0 ? "green" : "red"} style={{ marginLeft: 8 }}>
                    较本次 {delta >= 0 ? "+" : ""}
                    {delta.toFixed(1)} 分
                  </Tag>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {evidence.length > 0 && (
        <div className="evaluation-block">
          <Text strong>题目证据：</Text>
          <ul className="compact-list">
            {evidence.map((item, index) => (
              <li key={`${item.question}-${index}`}>
                <div>
                  <Text strong>
                    {index + 1}. {item.question}
                  </Text>
                  {typeof item.score === "number" && (
                    <Tag color={evaluationTagColor(item.score)} style={{ marginLeft: 8 }}>
                      {item.score.toFixed(1)} 分
                    </Tag>
                  )}
                </div>
                {item.answer ? (
                  <div>
                    <Text type="secondary">
                      回答：
                      {item.answer.length > 200 ? `${item.answer.slice(0, 200)}…` : item.answer}
                    </Text>
                  </div>
                ) : null}
                {item.rubric_evidence && item.rubric_evidence.length > 0 && (
                  <div>
                    <Text type="secondary">评分依据：{item.rubric_evidence.join("；")}</Text>
                  </div>
                )}
                {item.source_question_id && (
                  <Tag style={{ marginTop: 4 }}>题库：{item.source_question_id}</Tag>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function evaluationTagColor(score: number) {
  if (score >= 85) return "green";
  if (score >= 70) return "blue";
  if (score >= 50) return "orange";
  return "red";
}

function taskStatusColor(status: string) {
  if (["running", "success", "completed"].includes(status)) return "green";
  if (["not_enabled", "no_task"].includes(status)) return "default";
  if (["partial_success"].includes(status)) return "blue";
  if (["auth_required", "captcha_required", "rate_limited"].includes(status.toLowerCase())) return "orange";
  return "red";
}

function taskStatusText(status: string) {
  const names: Record<string, string> = {
    running: "运行中",
    not_enabled: "未启用",
    no_task: "暂无任务",
    completed: "已完成",
    success: "成功",
    partial_success: "部分成功",
    failed: "失败"
  };
  return names[status.toLowerCase()] ?? status;
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

function resumeSourceText(sourceType?: string) {
  if (sourceType === "job_upload") return "岗位上传简历";
  if (sourceType === "job_copy") return "岗位专属版本";
  if (sourceType === "uploaded") return "默认简历";
  return "简历";
}

function networkModeText(mode: ModelProvider["network_mode"]) {
  if (mode === "direct") return "直连";
  if (mode === "manual_proxy") return "手动代理";
  return "自动";
}


function sectionTitle(section: SectionKey) {
  if (section === "config") return "基础配置";
  if (section === "history") return "搜索历史";
  if (section === "job_pool") return "岗位池";
  if (section === "interview") return "模拟面试";
  if (section === "interview_history") return "面试历史";
  if (section === "tasks") return "任务状态";
  return "岗位搜索";
}

function sectionDescription(section: SectionKey) {
  if (section === "config") return "维护个人求职偏好、AI 模型和默认简历，后续评测都会读取这里的配置。";
  if (section === "history") return "按搜索时间倒序查看每次采集记录；展开后可继续 AI 测评或后续投递。";
  if (section === "job_pool") return "集中管理已确认投递岗位，并复用同一份 AI 测评和简历建议。";
  if (section === "interview") return "围绕岗位 JD、默认简历和题库进行多轮问答，并在结束后生成评分报告。";
  if (section === "interview_history") return "独立查看、删除和批量管理已提交过回答的模拟面试记录。";
  if (section === "tasks") return "查看本地任务执行器、Celery 队列状态、最近采集和最近模拟面试。";
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

function dateInputValue(value?: string | null) {
  return value ? value.slice(0, 10) : "";
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
    RATE_LIMITED: "Boss 采集过于频繁，请稍后再试。",
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
    failed: "失败",
    AUTH_REQUIRED: "需要登录",
    CAPTCHA_REQUIRED: "需要安全验证",
    RATE_LIMITED: "已限速",
    SOURCE_CHANGED: "页面结构变化",
    NO_RESULT: "无结果"
  };
  return statusMap[status] ?? status;
}

function collectionStatusColor(status: string) {
  if (status === "success") return "green";
  if (status === "partial_success") return "blue";
  if (status === "created") return "default";
  if (["AUTH_REQUIRED", "CAPTCHA_REQUIRED", "RATE_LIMITED"].includes(status)) return "orange";
  return "red";
}

function collectionStatusAlertType(status: string): "success" | "info" | "warning" | "error" {
  if (status === "success") return "success";
  if (status === "partial_success") return "warning";
  if (status === "created") return "info";
  return "error";
}








