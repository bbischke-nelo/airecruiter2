// Common types used across the application

export interface PaginationMeta {
  page: number;
  perPage: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginationMeta;
}

export interface Requisition {
  id: number;
  externalId: string;
  name: string;
  description: string | null;
  detailedDescription: string | null;
  location: string | null;
  department: string | null;
  isActive: boolean;
  syncEnabled: boolean;
  autoSendInterview: boolean;
  autoSendOnStatus: string | null;
  lookbackHours: number;
  recruiterId: number | null;
  applicationCount: number;
  lastSyncedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Application {
  id: number;
  requisitionId: number;
  externalApplicationId: string;
  externalCandidateId: string;
  candidateName: string;
  candidateEmail: string;
  status: ApplicationStatus;
  workdayStatus: string;
  riskScore: number | null;
  interviewSent: boolean;
  interviewSentAt: string | null;
  humanRequested: boolean;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

export type ApplicationStatus =
  | 'new'
  | 'analyzed'
  | 'interview_pending'
  | 'interview_complete'
  | 'report_pending'
  | 'complete';

export interface Analysis {
  id: number;
  applicationId: number;
  riskScore: number;
  relevanceSummary: string;
  pros: string[];
  cons: string[];
  redFlags: string[];
  suggestedQuestions: string[];
  createdAt: string;
}

export interface Interview {
  id: number;
  applicationId: number;
  candidateName: string;
  requisitionName: string;
  interviewType: string;
  token: string;
  tokenExpiresAt: string;
  status: InterviewStatus;
  startedAt: string | null;
  completedAt: string | null;
  humanRequested: boolean;
  humanRequestedAt: string | null;
  personaId: number | null;
  messageCount: number;
  createdAt: string;
}

export type InterviewStatus = 'scheduled' | 'in_progress' | 'completed' | 'abandoned';

export interface Message {
  id: number;
  interviewId: number;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

export interface Evaluation {
  id: number;
  interviewId: number;
  reliabilityScore: number;
  accountabilityScore: number;
  professionalismScore: number;
  communicationScore: number;
  technicalScore: number;
  growthPotentialScore: number;
  overallScore: number;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  redFlags: string[];
  recommendation: 'recommend' | 'consider' | 'do_not_recommend';
  createdAt: string;
}

export interface Recruiter {
  id: number;
  externalId: string | null;
  name: string;
  email: string;
  role: 'admin' | 'recruiter';
  isActive: boolean;
  createdAt: string;
}

export interface Prompt {
  id: number;
  name: string;
  promptType: string;
  templateContent: string;
  requisitionId: number | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Persona {
  id: number;
  name: string;
  description: string;
  systemPrompt: string;
  isActive: boolean;
  isDefault: boolean;
  createdAt: string;
}

export interface QueueItem {
  id: number;
  jobType: string;
  applicationId: number | null;
  requisitionId: number | null;
  priority: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'dead';
  attempts: number;
  maxAttempts: number;
  lastError: string | null;
  scheduledFor: string;
  createdAt: string;
}

export interface Activity {
  id: number;
  action: string;
  applicationId: number | null;
  requisitionId: number | null;
  candidateName: string | null;
  requisitionName: string | null;
  details: Record<string, any> | null;
  createdAt: string;
}
