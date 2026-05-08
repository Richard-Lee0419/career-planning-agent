export type SkillStatus = 'acquired' | 'not acquired';

export interface UserProfile {
  name?: string | null;
  education_level?: string | null;
  major?: string | null;
  grade?: string | null;
  location?: string | null;
  current_skills: string[];
  certificates: string[];
  internship_experience?: string | null;
  soft_skills: string[];
  innovation_potential?: string | null;
  target_roles: string[];
  interests: string[];
  competitiveness_score: number;
}

export interface AccountInfo {
  id: number;
  username: string;
  created_at?: string | null;
}

export interface CurrentUserResponse {
  status: string;
  data: {
    account: AccountInfo;
    profile: {
      name?: string | null;
      major?: string | null;
      education_level?: string | null;
      has_profile: boolean;
    };
  };
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: 'bearer';
}

export interface GraphSkill {
  name: string;
  isMastered: boolean;
}

export interface CareerLevel {
  id: string;
  level: string;
  title: string;
  status: SkillStatus;
  salaryRange: string;
  coreSkills: GraphSkill[];
  nextLevels?: string[];
}

export interface CareerGraphData {
  type?: 'career_map' | string;
  levels: CareerLevel[];
}

export interface MockInterviewGraphData {
  type: 'mock_interview';
  role: string;
  questions: string[];
}

export type GraphData = CareerGraphData | MockInterviewGraphData | Record<string, unknown>;

export interface ChatRequest {
  session_id?: string | null;
  message: string;
  profile?: UserProfile | null;
  graph_data?: GraphData | null;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  graph_data?: GraphData | null;
  blocks: unknown[];
}

export interface GapDimension {
  score: number;
  analysis: string;
  suggestions: string[];
}

export interface GapAnalysisResponse {
  target_role: string;
  overall_match_score: number;
  basic_matching: GapDimension;
  skill_matching: GapDimension;
  soft_skill_matching: GapDimension;
  potential_matching: GapDimension;
  immediate_next_steps: string[];
  roadmap_preview: string;
}

export interface LearningMilestone {
  phase: string;
  period: string;
  focus_targets: string[];
  recommended_resources: string[];
}

export interface LearningPathResponse {
  target_role: string;
  summary: string;
  milestones: LearningMilestone[];
  conclusion: string;
}

export interface JobItem {
  title: string;
  location: string;
  salary_range: string;
  company: string;
}

export interface JobsResponse {
  status: string;
  data: JobItem[];
  total_returned: number;
}

export interface JobStatsItem {
  name: string;
  value: number;
}

export interface JobStatsResponse {
  status: string;
  chart_type: 'pie';
  data: JobStatsItem[];
}

export interface GeneralQuestionItem {
  id: number;
  topic: string;
  question: string;
  audio_url?: string | null;
}

export interface GeneralInterviewResponse {
  role: string;
  questions: GeneralQuestionItem[];
}

export interface MockEvaluation {
  score: number;
  evaluation: string;
  improvement_suggestion: string;
  reference_answer: string;
}

export interface TargetedInterviewQuestion {
  role: string;
  difficulty: string;
  question: string;
  focus_topic: string;
  background_context: string;
}

export interface TargetedInterviewResponse {
  question_data: TargetedInterviewQuestion;
  audio_url?: string | null;
}

export interface InterviewHistoryItem {
  id: number;
  question: string;
  user_answer: string;
  score: number;
  evaluation: string;
  improvement_suggestion: string;
  reference_answer: string;
}

export interface InterviewHistoryResponse {
  status: string;
  count: number;
  data: InterviewHistoryItem[];
}

export interface RoadmapHistoryItem {
  id: number;
  role_name: string;
  roadmap_detail: Record<string, unknown>;
}

export interface RoadmapHistoryResponse {
  status: string;
  count: number;
  data: RoadmapHistoryItem[];
}

export interface ProfileExtractResponse {
  profile: UserProfile;
  is_complete: boolean;
  missing_fields: string[];
  next_questions: string[];
}

export interface SyncProfileResponse {
  status: string;
  message: string;
  new_score: number;
  detected_updates: {
    current_skills?: string[];
    certificates?: string[];
    internship_experience?: string;
  };
}

export interface SttResponse {
  text?: string;
  error?: string;
}
