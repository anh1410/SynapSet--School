import { useEffect, useState } from "react";
import { clearSession, getToken } from "@/lib/session";

const BASE = "/api/v1";

export class AuthError extends Error {}

// ---------- Shared enums ----------

export type BloomLevel = 1 | 2 | 3 | 4 | 5 | 6;

export const BLOOM_LEVELS: BloomLevel[] = [1, 2, 3, 4, 5, 6];

export const BLOOM_LABELS: Record<BloomLevel, string> = {
  1: "Remember",
  2: "Understand",
  3: "Apply",
  4: "Analyze",
  5: "Evaluate",
  6: "Create",
};

export type QuestionType =
  | "mcq"
  | "short_answer"
  | "long_answer"
  | "numerical"
  | "fill_in_blank"
  | "match_following"
  | "true_false"
  | "stem_diagram"
  | "visual_worksheet";

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  mcq: "Multiple Choice",
  short_answer: "Short Answer",
  long_answer: "Long Answer",
  numerical: "Numerical",
  fill_in_blank: "Fill in the Blanks",
  match_following: "Match the Following",
  true_false: "True or False",
  stem_diagram: "STEM / Math Diagram",
  visual_worksheet: "Visual Worksheet (LKG/UKG)",
};

// Canonical display order for question formats, shared by the Builder and Bank pages.
export const QUESTION_TYPE_ORDER: QuestionType[] = [
  "fill_in_blank",
  "match_following",
  "true_false",
  "short_answer",
  "long_answer",
  "mcq",
  "numerical",
  "stem_diagram",
  "visual_worksheet",
];

export type Difficulty = "easy" | "medium" | "hard";

export const DIFFICULTY_LEVELS: Difficulty[] = ["easy", "medium", "hard"];

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

// Languages Gemini is explicitly instructed to write question text/options/answers
// in (see the LANGUAGE section of GENERATION_PROMPT). "English" is the default and
// matches prior behavior exactly. Hindi/Kannada also get proper OpenType-shaped
// rendering in exported PDFs (see indic_text.py) - other scripts aren't wired up yet.
export const LANGUAGES = ["English", "Hindi", "Kannada"] as const;
export type Language = (typeof LANGUAGES)[number];

// Sensible default marks per format — always editable by the teacher, not locked.
export const DEFAULT_MARKS: Record<QuestionType, number> = {
  fill_in_blank: 1,
  true_false: 1,
  match_following: 1,
  short_answer: 3,
  long_answer: 7,
  mcq: 4,
  numerical: 4,
  stem_diagram: 5,
  visual_worksheet: 1,
};

// ---------- School year & term ----------

// Keep in step with TERMS in app/core/academic.py.
export const TERMS = ["Term 1", "Term 2", "Annual"] as const;

/** The Indian school year runs June-May: October 2026 is "2026-27", so is February 2027. */
export function academicYearFor(date: Date = new Date()): string {
  const start = date.getMonth() >= 5 ? date.getFullYear() : date.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

// ---------- Core resources ----------

export interface MatchPair {
  left: string;
  right: string;
}

export type DiagramKind = "matplotlib" | "tikz" | "image"; // "image" = a picture a teacher uploaded

export interface DiagramSpec {
  kind: DiagramKind;
  source_code: string;
  image_id: string | null;
  caption: string | null;
  render_error: string | null;
}

export interface VisualPrompt {
  subject: string;
  style: string;
  action: string | null;
  background: string | null;
  full_prompt: string;
  image_id: string | null;
}

export interface GridItem {
  visual: VisualPrompt;
  label: string | null;
  is_correct: boolean | null;
}

export type GridLayoutKind = "grid_2x4" | "two_column_match" | "single_row";
export type ResponseStyle = "circle_choice" | "blank_line" | "match_lines";

export interface GridLayout {
  kind: GridLayoutKind;
  items: GridItem[];
  response_style: ResponseStyle;
  instruction: string | null;
}

export interface Question {
  id: string;
  subject_id: string;
  text: string;
  question_type: QuestionType;
  marks: number;
  bloom_level: BloomLevel;
  topic_ids: string[];
  co_ids: string[];
  unit: number | null;
  options: string[] | null;
  correct_answer: string | null;
  match_pairs: MatchPair[] | null;
  match_right_order: number[] | null;
  is_true: boolean | null;
  difficulty_score: number | null;
  embedding_id: string | null;
  is_duplicate_of: string | null;
  source_document: string | null;
  author_id?: string | null; // the teacher who submitted it, when it came from a submission
  academic_year?: string | null; // e.g. "2026-27", set automatically
  term?: string | null;
  created_at: string;
  diagram: DiagramSpec | null;
  grid_layout: GridLayout | null;
}

export interface DifficultyScore {
  score: number;
  features: Record<string, number>;
  shap_contributions: Record<string, number> | null;
  method: "heuristic" | "model";
}

export interface DuplicateMatch {
  existing_question_id: string;
  semantic_score: number;
  graph_score: number;
  structural_score: number;
  final_score: number;
  is_duplicate: boolean;
}

export interface GeneratedQuestionResult {
  question: Question;
  difficulty: DifficultyScore;
  duplicate_matches: DuplicateMatch[];
}

export interface GraphNode {
  id: string;
  name: string;
  description: string;
  importance_score: number;
  question_count: number;
  coverage_pct: number;
  degree: number;
  neglected: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation_type: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type DocumentCategory = "syllabus" | "notes" | "papers";
export type DocumentStatus = "processing" | "processed" | "failed";

export interface UploadedDocument {
  id: string;
  subject_id: string;
  filename: string;
  category: DocumentCategory;
  size_bytes: number;
  status: DocumentStatus;
  topics_extracted: number;
  error_message: string | null;
  uploaded_at: string;
}

export type BlueprintStatus = "draft" | "exported";

export interface BlueprintSection {
  id: string;
  title: string;
  question_format: QuestionType;
  question_ids: string[];
}

export interface PaperBlueprint {
  id: string;
  teacher_id: string;
  subject_id: string;
  name: string;
  total_marks: number;
  duration_minutes: number | null;
  sections: BlueprintSection[];
  question_ids: string[];
  status: BlueprintStatus;
  academic_year: string; // defaults to the year it was made in
  term: string | null;
  created_at: string;
  updated_at: string;
}

// ---------- Builder drafts ----------

export type SectionMode = "specific" | "random";

export interface DraftQuestionSpec {
  id: string;
  topic_id: string;
  difficulty: Difficulty;
}

export interface DraftSection {
  id: string;
  question_format: QuestionType;
  mode: SectionMode;
  questions: DraftQuestionSpec[]; // mode === "specific"
  topic_ids: string[]; // mode === "random"
  difficulty: Difficulty; // mode === "random"
  count: number; // mode === "random"
  marks_per_question: number;
  generated_question_ids: string[];
  language: Language;
}

export interface BuilderDraft {
  id: string;
  teacher_id: string;
  subject_id: string;
  paper_name: string;
  duration_minutes: number | null;
  sections: DraftSection[];
  updated_at: string;
}

export function getDraft(subjectId: string) {
  return apiFetch<BuilderDraft | null>(`/drafts?subject_id=${encodeURIComponent(subjectId)}`);
}

export function putDraft(draft: BuilderDraft) {
  return apiFetch<BuilderDraft>("/drafts", { method: "PUT", body: JSON.stringify(draft) });
}

export function deleteDraft(subjectId: string) {
  return apiFetch<{ cleared: boolean }>(`/drafts?subject_id=${encodeURIComponent(subjectId)}`, { method: "DELETE" });
}

// ---------- Paper templates (reusable section patterns, teacher-scoped) ----------

export interface TemplateSection {
  question_format: QuestionType;
  mode: SectionMode;
  difficulties: Difficulty[]; // mode === "specific": one entry per planned question
  difficulty: Difficulty; // mode === "random"
  count: number; // mode === "random"
  marks_per_question: number;
  language: Language;
}

export interface PaperTemplate {
  id: string;
  teacher_id: string;
  name: string;
  duration_minutes: number | null;
  sections: TemplateSection[];
  created_at: string;
}

export function listTemplates() {
  return apiFetch<PaperTemplate[]>("/templates");
}

export function createTemplate(data: { name: string; duration_minutes?: number | null; sections: TemplateSection[] }) {
  return apiFetch<PaperTemplate>("/templates", { method: "POST", body: JSON.stringify(data) });
}

export function deleteTemplate(id: string) {
  return apiFetch<{ deleted: string }>(`/templates/${id}`, { method: "DELETE" });
}

export interface BloomDistribution {
  weights: Partial<Record<BloomLevel, number>>;
}

export interface PaperConstraints {
  total_marks: number;
  bloom_distribution: BloomDistribution;
  co_coverage?: Record<string, number>;
  unit_marks?: Record<string, number>;
  num_questions?: number | null;
  allowed_question_types?: QuestionType[] | null;
}

// ---------- fetch helpers ----------

class ApiError extends Error {}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...authHeaders(),
      ...options.headers,
    },
  });
  if (res.status === 401) {
    clearSession();
    window.dispatchEvent(new Event("synapset-school:session-expired"));
    throw new AuthError("Session expired, please log in again");
  }
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const parsed = JSON.parse(text);
      message = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail ?? parsed);
    } catch {
      // not json, use raw text
    }
    throw new ApiError(message || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Fetches an image by id with the auth header attached (an <img src> can't carry one)
 *  and hands back an object URL. Returns null while loading or if imageId is null/fetch fails. */
export function useImageUrl(imageId: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!imageId) {
      setUrl(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    fetch(`${BASE}/images/${imageId}`, { headers: authHeaders() })
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error("image fetch failed"))))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageId]);

  return url;
}

async function downloadFromResponse(res: Response, fallbackName: string) {
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(text || `${res.status} ${res.statusText}`);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition");
  const match = disposition?.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------- Auth ----------

export interface AuthResponse {
  access_token: string;
  teacher: import("@/lib/session").TeacherPublic;
}

export function signup(email: string, password: string, name: string) {
  return apiFetch<AuthResponse>("/auth/signup", { method: "POST", body: JSON.stringify({ email, password, name }) });
}

export function login(email: string, password: string) {
  return apiFetch<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

export function me() {
  return apiFetch<import("@/lib/session").TeacherPublic>("/auth/me");
}

/** Public signup only exists to create the very first account (the admin). */
export function signupStatus() {
  return apiFetch<{ signup_open: boolean }>("/auth/signup-status");
}

// ---------- Subjects ----------

// Karnataka-style school: LKG, UKG, then classes 1-10. Must match GRADES in app/schemas/subject.py.
export const GRADES = ["LKG", "UKG", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"] as const;
export type Grade = (typeof GRADES)[number];

export const gradeLabel = (grade: string | null | undefined): string =>
  !grade ? "" : grade === "LKG" || grade === "UKG" ? grade : `Grade ${grade}`;

export interface Subject {
  id: string;
  teacher_id: string; // the admin who created it - not an access grant
  name: string;
  grade: string | null; // null only for subjects created before grades existed
  created_at: string;
}

/** "Maths · Grade 5", or just the name for an old subject with no grade yet. */
export const subjectLabel = (s: Pick<Subject, "name" | "grade">): string =>
  s.grade ? `${s.name} · ${gradeLabel(s.grade)}` : s.name;

/** Subjects grouped for display in school order: LKG, UKG, 1..10, then any with no grade yet. */
export function groupSubjectsByGrade<T extends Pick<Subject, "grade">>(
  subjects: T[]
): { grade: string | null; subjects: T[] }[] {
  const groups = GRADES.map((g) => ({ grade: g as string | null, subjects: subjects.filter((s) => s.grade === g) }));
  groups.push({ grade: null, subjects: subjects.filter((s) => !s.grade || !(GRADES as readonly string[]).includes(s.grade)) });
  return groups.filter((g) => g.subjects.length > 0);
}

export function listSubjects() {
  return apiFetch<Subject[]>("/subjects");
}

export function createSubject(name: string, grade: string) {
  return apiFetch<Subject>("/subjects", { method: "POST", body: JSON.stringify({ name, grade }) });
}

export function updateSubject(id: string, data: { name?: string; grade?: string }) {
  return apiFetch<Subject>(`/subjects/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteSubject(id: string) {
  return apiFetch<{ deleted: string }>(`/subjects/${id}`, { method: "DELETE" });
}

// ---------- Admin: teacher accounts & subject assignments ----------

export interface AdminTeacher {
  id: string;
  email: string;
  name: string;
  role: "admin" | "teacher";
  active: boolean;
  created_at: string;
  subject_ids: string[];
  credit_count: number; // questions of theirs used in exported papers
}

export function listTeachers() {
  return apiFetch<AdminTeacher[]>("/admin/teachers");
}

export function createTeacher(data: { name: string; email: string; password: string; subject_ids: string[] }) {
  return apiFetch<AdminTeacher>("/admin/teachers", { method: "POST", body: JSON.stringify(data) });
}

export function updateTeacher(
  id: string,
  data: { name?: string; role?: "admin" | "teacher"; active?: boolean; password?: string }
) {
  return apiFetch<AdminTeacher>(`/admin/teachers/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteTeacher(id: string) {
  return apiFetch<{ deleted: string }>(`/admin/teachers/${id}`, { method: "DELETE" });
}

export function setTeacherSubjects(id: string, subjectIds: string[]) {
  return apiFetch<AdminTeacher>(`/admin/teachers/${id}/subjects`, {
    method: "PUT",
    body: JSON.stringify({ subject_ids: subjectIds }),
  });
}

// ---------- Graph & documents ----------

export function fetchGraph(subjectId: string) {
  return apiFetch<GraphResponse>(`/graph?subject_id=${encodeURIComponent(subjectId)}`);
}

export function fetchDocuments(subjectId: string) {
  return apiFetch<UploadedDocument[]>(`/graph/documents?subject_id=${encodeURIComponent(subjectId)}`);
}

export function deleteDocument(id: string) {
  return apiFetch<{ deleted: string }>(`/graph/documents/${id}`, { method: "DELETE" });
}

export interface IngestResult {
  document: UploadedDocument;
  retrieval_chunks_indexed: number;
  extraction_chunks_processed: number;
  graph_nodes: number;
  graph_edges: number;
}

export function ingestDocument(file: File, category: DocumentCategory, subjectId: string, courseOutcomes?: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  form.append("subject_id", subjectId);
  if (courseOutcomes) form.append("course_outcomes", courseOutcomes);
  return apiFetch<IngestResult>("/graph/ingest", { method: "POST", body: form });
}

export interface DedupeTopicsResult {
  merged_groups: number;
  nodes_removed: number;
  questions_updated: number;
}

export function dedupeTopics(subjectId: string) {
  return apiFetch<DedupeTopicsResult>(`/graph/dedupe-topics?subject_id=${encodeURIComponent(subjectId)}`, {
    method: "POST",
  });
}

// ---------- Questions ----------

export interface GenerateQuestionsParams {
  subject_id: string;
  topic: string;
  num_questions: number;
  bloom_level?: BloomLevel;
  marks: number;
  question_type: QuestionType;
  difficulty?: Difficulty;
  language?: Language;
  check_duplicates?: boolean;
  save_to_bank?: boolean;
}

export function generateQuestions(params: GenerateQuestionsParams) {
  return apiFetch<{ results: GeneratedQuestionResult[] }>("/questions/generate", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export interface GenerateSectionParams {
  subject_id: string;
  topic_ids: string[];
  question_type: QuestionType;
  num_questions: number;
  difficulty: Difficulty;
  marks: number;
  bloom_level?: BloomLevel;
  language?: Language;
  check_duplicates?: boolean;
  save_to_bank?: boolean;
}

export function generateSection(params: GenerateSectionParams) {
  return apiFetch<{ results: GeneratedQuestionResult[] }>("/questions/generate-section", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function fetchQuestions(subjectId: string) {
  return apiFetch<Question[]>(`/questions?subject_id=${encodeURIComponent(subjectId)}`);
}

export function saveQuestion(question: Question) {
  return apiFetch<Question>("/questions", { method: "POST", body: JSON.stringify(question) });
}

export function deleteQuestion(id: string) {
  return apiFetch<{ deleted: string }>(`/questions/${id}`, { method: "DELETE" });
}

export function bulkDeleteQuestions(ids: string[]) {
  return apiFetch<{ deleted: string[] }>("/questions/bulk-delete", {
    method: "POST",
    body: JSON.stringify({ question_ids: ids }),
  });
}

export function checkDuplicates(question: Question, threshold = 0.75) {
  return apiFetch<{ matches: DuplicateMatch[] }>("/questions/check-duplicates", {
    method: "POST",
    body: JSON.stringify({ question, threshold }),
  });
}

// ---------- Paper: optimize & export ----------

export function optimizePaper(subjectId: string, constraints: PaperConstraints, questionIds?: string[]) {
  return apiFetch<{ status: string; selected: Question[] }>("/paper/optimize", {
    method: "POST",
    body: JSON.stringify({ subject_id: subjectId, constraints, question_ids: questionIds }),
  });
}

export async function exportPaperAdhoc(title: string, questions: Question[], format: "pdf" | "docx") {
  const res = await fetch(`${BASE}/paper/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ title, questions, format }),
  });
  await downloadFromResponse(res, `${title}.${format}`);
}

export interface BlueprintSectionInput {
  title: string;
  question_format: QuestionType;
  question_ids: string[];
}

export function createBlueprint(data: {
  subject_id: string;
  name: string;
  total_marks: number;
  duration_minutes?: number;
  academic_year?: string;
  term?: string;
  sections: BlueprintSectionInput[];
}) {
  return apiFetch<PaperBlueprint>("/paper/blueprints", { method: "POST", body: JSON.stringify(data) });
}

export function listBlueprints(subjectId: string) {
  return apiFetch<PaperBlueprint[]>(`/paper/blueprints?subject_id=${encodeURIComponent(subjectId)}`);
}

export function getBlueprint(id: string) {
  return apiFetch<{ blueprint: PaperBlueprint; questions: Question[] }>(`/paper/blueprints/${id}`);
}

export function updateBlueprint(
  id: string,
  data: Partial<{
    name: string;
    total_marks: number;
    duration_minutes: number;
    sections: BlueprintSectionInput[];
    status: BlueprintStatus;
    academic_year: string;
    term: string; // "" clears it
  }>
) {
  return apiFetch<PaperBlueprint>(`/paper/blueprints/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteBlueprint(id: string) {
  return apiFetch<{ deleted: string }>(`/paper/blueprints/${id}`, { method: "DELETE" });
}

export type ExportVariant = "student" | "answer_key";

export async function exportBlueprint(id: string, name: string, format: "pdf" | "docx", variant: ExportVariant = "student") {
  const res = await fetch(`${BASE}/paper/blueprints/${id}/export?format=${format}&variant=${variant}`, {
    headers: authHeaders(),
  });
  const suffix = variant === "answer_key" ? "_answer_key" : "";
  await downloadFromResponse(res, `${name}${suffix}.${format}`);
}

// ---------- Images (teacher uploads) ----------

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // keep in step with image_store.MAX_UPLOAD_BYTES

export function uploadImage(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<{ image_id: string }>("/images", { method: "POST", body: form });
}

// ---------- Submissions ----------

export type SubmissionStatus = "submitted" | "changes_requested" | "accepted" | "rejected";

export const SUBMISSION_STATUS_LABELS: Record<SubmissionStatus, string> = {
  submitted: "Waiting for review",
  changes_requested: "Changes requested",
  accepted: "Accepted",
  rejected: "Rejected",
};

/** What a teacher is allowed to send; mirrors SubmittedQuestion in app/schemas/submission.py. */
export interface SubmittedQuestion {
  text: string;
  question_type: QuestionType;
  marks: number;
  difficulty: Difficulty;
  term?: string | null;
  topic_ids: string[];
  options?: string[] | null;
  correct_answer?: string | null;
  match_pairs?: MatchPair[] | null;
  is_true?: boolean | null;
  diagram?: { image_id: string; caption?: string | null } | null;
  grid_layout?: {
    kind: GridLayoutKind;
    response_style: ResponseStyle;
    items: { image_id: string; label?: string | null; is_correct?: boolean | null }[];
  } | null;
}

export interface SubmissionEvent {
  at: string;
  kind: "submitted" | "edited" | "resubmitted" | "changes_requested" | "accepted" | "rejected";
  by: string;
  by_name: string;
  comment: string | null;
}

/** A near-identical question already in the bank or waiting in the inbox. Admins only. */
export interface DuplicateHit {
  question_id: string;
  text: string;
  similarity: number;
  where: "bank" | "pending";
}

export interface Submission {
  id: string;
  subject_id: string;
  subject_name: string;
  subject_grade: string | null;
  teacher_id: string;
  teacher_name: string;
  status: SubmissionStatus;
  question: Question;
  admin_comment: string | null;
  reviewed_at: string | null;
  revision: number;
  history: SubmissionEvent[];
  created_at: string;
  updated_at: string;
  duplicate_hits: DuplicateHit[];
}

export interface SubmissionSummary {
  submitted: number;
  changes_requested: number;
  accepted: number;
  rejected: number;
}

export interface SubmissionFilters {
  subject_id?: string;
  grade?: string;
  teacher_id?: string;
  status?: SubmissionStatus;
  question_type?: QuestionType;
  q?: string;
}

export function listSubmissions(filters: SubmissionFilters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
  const qs = params.toString();
  return apiFetch<Submission[]>(`/submissions${qs ? `?${qs}` : ""}`);
}

export function submissionSummary() {
  return apiFetch<SubmissionSummary>("/submissions/summary");
}

export function createSubmission(subjectId: string, question: SubmittedQuestion) {
  return apiFetch<Submission>("/submissions", {
    method: "POST",
    body: JSON.stringify({ subject_id: subjectId, question }),
  });
}

export function updateSubmission(id: string, question: SubmittedQuestion) {
  return apiFetch<Submission>(`/submissions/${id}`, { method: "PUT", body: JSON.stringify({ question }) });
}

/** Admin only: fix a waiting submission (typo, wrong answer) instead of sending it back. */
export function adminEditSubmission(id: string, question: SubmittedQuestion) {
  return apiFetch<Submission>(`/submissions/${id}/question`, { method: "PATCH", body: JSON.stringify({ question }) });
}

export function deleteSubmission(id: string) {
  return apiFetch<{ deleted: string }>(`/submissions/${id}`, { method: "DELETE" });
}

export function reviewSubmission(id: string, decision: "accept" | "reject" | "request_changes", comment?: string) {
  return apiFetch<Submission>(`/submissions/${id}/review`, {
    method: "POST",
    body: JSON.stringify({ decision, comment: comment ?? null }),
  });
}

export function listSubjectTopics(subjectId: string) {
  return apiFetch<{ id: string; name: string }[]>(`/subjects/${subjectId}/topics`);
}

// ---------- Activity log (admin) ----------

export interface AuditEntry {
  id: string;
  at: string;
  actor_id: string;
  actor_name: string;
  action: string; // "<area>.<verb>"
  target_type: string;
  target_id: string;
  summary: string;
}

export const AUDIT_AREAS: { id: string; label: string }[] = [
  { id: "question", label: "Question bank" },
  { id: "submission", label: "Submissions" },
  { id: "paper", label: "Papers" },
  { id: "teacher", label: "Teachers" },
  { id: "subject", label: "Subjects" },
];

export function listAudit(filters: { actor_id?: string; area?: string; q?: string; before?: string; limit?: number }) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, String(value));
  return apiFetch<{ items: AuditEntry[]; has_more: boolean }>(`/admin/audit?${params.toString()}`);
}

// ---------- Credits ----------

/** One credit: a question of the teacher's that was used in an exported paper.
 *  Only the exam's name is exposed, never what else is on it. */
export interface Credit {
  id: string;
  question_id: string;
  question_text: string;
  question_type: QuestionType;
  marks: number;
  exam_name: string;
  subject_name: string;
  subject_grade: string | null;
  earned_at: string;
}

export function listCredits() {
  return apiFetch<{ total: number; items: Credit[] }>("/credits");
}

// ---------- Display helpers ----------

export type DifficultyBucket = "Easy" | "Medium" | "Hard";

export function difficultyBucket(score: number | null | undefined): DifficultyBucket {
  if (score == null) return "Medium";
  if (score <= 4) return "Easy";
  if (score <= 7) return "Medium";
  return "Hard";
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return new Date(iso).toLocaleDateString();
}

const ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"];

export function toRoman(index: number): string {
  return `(${ROMAN[index] ?? String(index + 1)})`;
}

export function toLetter(index: number): string {
  return String.fromCharCode(65 + index);
}

export interface MatchColumns {
  columnA: { label: string; text: string }[];
  columnB: { label: string; text: string }[];
  /** left index (Column A row) -> correct Column B letter, for answer-key display */
  correctLetter: Record<number, string>;
}

/** Column A stays in original order; Column B is shuffled per match_right_order
 *  (falls back to identity order for older data saved before this field existed)
 *  so the two columns line up the same way the backend's PDF/DOCX export does. */
export function matchColumns(q: Question): MatchColumns {
  const pairs = q.match_pairs ?? [];
  const order = q.match_right_order && q.match_right_order.length === pairs.length ? q.match_right_order : pairs.map((_, i) => i);

  const columnA = pairs.map((p, i) => ({ label: toRoman(i), text: p.left }));
  const columnB = order.map((origIdx, pos) => ({ label: `${toLetter(pos)})`, text: pairs[origIdx].right }));
  const correctLetter: Record<number, string> = {};
  order.forEach((origIdx, pos) => {
    correctLetter[origIdx] = toLetter(pos);
  });

  return { columnA, columnB, correctLetter };
}

export { ApiError };
