import { apiClient } from './client';
import type {
  GeneralInterviewResponse,
  InterviewHistoryResponse,
  MockEvaluation,
  SttResponse,
  TargetedInterviewResponse
} from './types';

export async function fetchInterviewQuestions(targetRole: string, focusTopics: string) {
  const { data } = await apiClient.get<GeneralInterviewResponse>('/api/interview/questions', {
    params: { target_role: targetRole, focus_topics: focusTopics }
  });
  return data;
}

export async function fetchTargetedQuestion(targetRole: string) {
  const { data } = await apiClient.get<TargetedInterviewResponse>('/api/interview/generate-targeted', {
    params: { target_role: targetRole }
  });
  return data;
}

export async function evaluateInterviewAnswer(payload: {
  target_role: string;
  question: string;
  user_answer: string;
  focus_area?: string;
}) {
  const { data } = await apiClient.post<MockEvaluation>('/api/agent/mock-interview/evaluate', payload);
  return data;
}

export async function speechToText(file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<SttResponse>('/api/audio/stt', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return data;
}

export async function fetchInterviewHistory() {
  const { data } = await apiClient.get<InterviewHistoryResponse>('/api/history/interviews');
  return data;
}
