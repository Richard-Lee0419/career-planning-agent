import { apiClient } from './client';
import type {
  GeneralInterviewResponse,
  InterviewHistoryResponse,
  MockEvaluation,
  SttResponse,
  TargetedInterviewResponse
} from './types';
import { useAuthStore } from '../store/authStore';

const pendingEvaluationKeys = new Map<string, string>();
const pendingEvaluations = new Map<string, Promise<MockEvaluation>>();

export async function fetchInterviewQuestions(targetRole: string, focusTopics: string) {
  const { data } = await apiClient.get<GeneralInterviewResponse>('/api/interview/questions', {
    params: { target_role: targetRole, focus_topics: focusTopics }, timeout: 150000
  });
  return data;
}

export async function fetchTargetedQuestion(targetRole: string) {
  const { data } = await apiClient.get<TargetedInterviewResponse>('/api/interview/generate-targeted', {
    params: { target_role: targetRole }, timeout: 150000
  });
  return data;
}

export async function evaluateInterviewAnswer(payload: {
  target_role: string;
  question: string;
  user_answer: string;
  focus_area?: string;
}) {
  const fingerprint = `${useAuthStore.getState().token || ''}:${JSON.stringify(payload)}`;
  const inFlight = pendingEvaluations.get(fingerprint);
  if (inFlight) return inFlight;
  const key = pendingEvaluationKeys.get(fingerprint) || crypto.randomUUID();
  pendingEvaluationKeys.set(fingerprint, key);
  const request = apiClient.post<MockEvaluation>('/api/agent/mock-interview/evaluate', payload, {
    headers: { 'Idempotency-Key': key }, timeout: 150000
  }).then(({ data }) => {
    pendingEvaluationKeys.delete(fingerprint);
    return data;
  }).finally(() => pendingEvaluations.delete(fingerprint));
  pendingEvaluations.set(fingerprint, request);
  return request;
}

export async function speechToText(file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<SttResponse>('/api/audio/stt', form, {
    headers: { 'Content-Type': 'multipart/form-data' }, timeout: 150000
  });
  return data;
}

export type AudioJobStatus = 'pending' | 'success' | 'failed' | 'expired';

export async function fetchAudioStatus(audioUrl: string) {
  const filename = audioUrl.split('?')[0].split('/').pop();
  if (!filename) throw new Error('语音链接无效');
  const { data } = await apiClient.get<{ status: AudioJobStatus }>(
    `/api/audio/status/${encodeURIComponent(filename)}`
  );
  return data.status;
}

export async function fetchInterviewHistory() {
  const { data } = await apiClient.get<InterviewHistoryResponse>('/api/history/interviews');
  return data;
}
