'use client';

import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  ChevronLeft,
  ChevronRight,
  Briefcase,
  GraduationCap,
  Award,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  ExternalLink,
  Download,
  MessageSquare,
  Send,
  RotateCcw,
  Phone,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetBody, SheetFooter } from '@/components/ui/sheet';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Markdown } from '@/components/ui/markdown';
import { api } from '@/lib/api';
import { formatRelativeTime, cn } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';
import { RejectReasonSelector, type RejectionReasonCode } from './RejectReasonSelector';
import { SendInterviewModal } from './SendInterviewModal';

interface Application {
  id: number;
  externalApplicationId: string;
  candidateName: string;
  candidateEmail: string | null;
  requisitionId: number;
  requisitionName: string;
  status: string;
  workdayStatus: string | null;
  hasAnalysis: boolean;
  hasInterview: boolean;
  hasReport: boolean;
  // Grid triage columns
  jdMatchPercentage: number | null;
  avgTenureMonths: number | null;
  currentTitle: string | null;
  currentEmployer: string | null;
  totalExperienceMonths: number | null;
  monthsSinceLastEmployment: number | null;
  humanRequested: boolean;
  complianceReview: boolean;
  rejectionReasonCode: string | null;
  createdAt: string;
}

interface ExtractedFacts {
  id: number;
  applicationId: number;
  extractionVersion: string | null;
  extractionNotes: string | null;
  extractedFacts: {
    employment_history?: Array<{
      employer: string;
      title: string;
      start_date: string | null;
      end_date: string | null;
      duration_months: number;
      is_current: boolean;
    }>;
    skills?: {
      technical: string[];
      software: string[];
      industry_specific: string[];
    };
    certifications?: Array<{
      name: string;
      issuer: string | null;
      date_obtained: string | null;
    }>;
    licenses?: Array<{
      type: string;
      class: string | null;
      endorsements: string[];
    }>;
    education?: Array<{
      institution: string;
      degree: string | null;
      field: string | null;
      graduation_date: string | null;
    }>;
    summary_stats?: {
      total_experience_months: number;
      recent_5yr_employers_count: number;
      recent_5yr_average_tenure_months: number;
      most_recent_employer: string | null;
      most_recent_title: string | null;
      months_since_last_employment: number;
    };
    jd_requirements_match?: {
      requirements: Array<{
        requirement: string;
        category: string;
        met: 'yes' | 'no' | 'partial';
        evidence: string | null;
        explanation: string;
      }>;
      summary: {
        total_requirements: number;
        fully_met: number;
        partially_met: number;
        not_met: number;
        match_percentage: number;
      };
    };
  } | null;
  pros: Array<{ category: string; observation: string; evidence: string }>;
  cons: Array<{ category: string; observation: string; evidence: string }>;
  suggestedQuestions: Array<{ topic: string; question: string; reason: string }>;
  relevanceSummary: string | null;
  modelVersion: string | null;
  createdAt: string;
}

interface InterviewData {
  id: number;
  applicationId: number;
  interviewType: string;
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  messageCount: number;
}

interface EvaluationData {
  id: number;
  interviewId: number;
  summary: string | null;
  interviewHighlights: string[];
  nextInterviewFocus: string[];
}

interface DecisionResponse {
  success: boolean;
  applicationId: number;
  action: string;
  fromStatus: string;
  toStatus: string;
  message: string;
}

interface ApplicationDrawerProps {
  application: Application | null;
  applications: Application[];
  onClose: () => void;
  onNavigate: (app: Application) => void;
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  downloading: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  downloaded: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  extracting: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  extracted: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
  generating_summary: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
  ready_for_review: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
  advancing: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200',
  interview_sending: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200',
  interview_sent: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  interview_received: 'bg-lime-100 text-lime-800 dark:bg-lime-900 dark:text-lime-200',
  transcribing: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  interview_ready_for_review: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
  advanced: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  live_interview_pending: 'bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200',
  rejected: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  on_hold: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
  error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

const statusLabels: Record<string, string> = {
  new: 'New',
  downloading: 'Downloading Resume',
  downloaded: 'Downloaded',
  extracting: 'Extracting Facts',
  extracted: 'Extracted',
  generating_summary: 'Generating Summary',
  ready_for_review: 'Ready for Review',
  advancing: 'Advancing',
  interview_sending: 'Sending Interview',
  interview_sent: 'Interview Sent',
  interview_received: 'Interview Received',
  transcribing: 'Transcribing',
  interview_ready_for_review: 'Interview Ready for Review',
  advanced: 'Advanced',
  live_interview_pending: 'Live Interview Pending',
  rejected: 'Rejected',
  on_hold: 'On Hold',
  error: 'Error',
};

// Statuses that allow human decisions
const ADVANCE_VALID_STATUSES = ['ready_for_review', 'interview_ready_for_review', 'on_hold'];
const REJECT_VALID_STATUSES = ['ready_for_review', 'interview_ready_for_review', 'on_hold', 'new', 'extracted'];
const HOLD_VALID_STATUSES = ['ready_for_review', 'interview_ready_for_review'];

export function ApplicationDrawer({
  application,
  applications,
  onClose,
  onNavigate,
}: ApplicationDrawerProps) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { toast } = useToast();
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [showInterviewModal, setShowInterviewModal] = useState(false);
  const [showReconsiderDialog, setShowReconsiderDialog] = useState(false);
  const [reconsiderComment, setReconsiderComment] = useState('');
  const [activeTab, setActiveTab] = useState('screening');
  const [resumeUrl, setResumeUrl] = useState<string | null>(null);
  const [expandedRequirements, setExpandedRequirements] = useState<{
    met: boolean;
    partial: boolean;
    unmet: boolean;
  }>({ met: false, partial: false, unmet: false });

  // Find current index
  const currentIndex = application ? applications.findIndex((a) => a.id === application.id) : -1;
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < applications.length - 1;

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' && hasPrev) {
        onNavigate(applications[currentIndex - 1]);
      } else if (e.key === 'ArrowRight' && hasNext) {
        onNavigate(applications[currentIndex + 1]);
      } else if (e.key === 'Escape') {
        onClose();
      }
    },
    [hasPrev, hasNext, currentIndex, applications, onNavigate, onClose]
  );

  useEffect(() => {
    if (application) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [application, handleKeyDown]);

  // Reset tab and expanded state when application changes
  useEffect(() => {
    setActiveTab('screening');
    setExpandedRequirements({ met: false, partial: false, unmet: false });
  }, [application?.id]);

  // Fetch resume URL when application changes
  useEffect(() => {
    if (application) {
      setResumeUrl(null); // Reset while loading
      api.get(`/applications/${application.id}/resume/download`)
        .then((response) => {
          setResumeUrl(response.data.url);
        })
        .catch(() => {
          setResumeUrl(null);
        });
    } else {
      setResumeUrl(null);
    }
  }, [application?.id]);

  // Fetch extracted facts
  const { data: facts, isLoading: factsLoading } = useQuery<ExtractedFacts>({
    queryKey: ['application-facts', application?.id],
    queryFn: async () => {
      const response = await api.get(`/applications/${application?.id}/facts`);
      return response.data;
    },
    enabled: !!application,
  });

  // Fetch interview data if application has interview
  const { data: interviewData } = useQuery<{ interview: InterviewData; evaluation: EvaluationData | null } | null>({
    queryKey: ['application-interview', application?.id],
    queryFn: async () => {
      // Get interviews for this application
      const response = await api.get(`/interviews?application_id=${application?.id}`);
      const interviews = response.data.data;
      if (interviews.length === 0) return null;

      const interview = interviews[0];

      // Try to get evaluation
      let evaluation = null;
      try {
        const evalResponse = await api.get(`/interviews/${interview.id}/evaluation`);
        evaluation = evalResponse.data;
      } catch {
        // No evaluation yet
      }

      return { interview, evaluation };
    },
    enabled: !!application?.hasInterview,
  });

  // Mutations
  const advanceMutation = useMutation<DecisionResponse, Error, { skipInterview?: boolean }>({
    mutationFn: async ({ skipInterview = false }) => {
      const response = await api.post(`/applications/${application?.id}/advance`, {
        skipInterview,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      if (hasNext) {
        onNavigate(applications[currentIndex + 1]);
      } else {
        onClose();
      }
    },
  });

  const rejectMutation = useMutation<DecisionResponse, Error, { reasonCode: string }>({
    mutationFn: async ({ reasonCode }) => {
      const response = await api.post(`/applications/${application?.id}/reject`, {
        reasonCode,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      setShowRejectDialog(false);
      if (hasNext) {
        onNavigate(applications[currentIndex + 1]);
      } else {
        onClose();
      }
    },
  });

  const holdMutation = useMutation<DecisionResponse, Error, void>({
    mutationFn: async () => {
      const response = await api.post(`/applications/${application?.id}/hold`, {});
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
    },
  });

  const unrejectMutation = useMutation<DecisionResponse, Error, { comment: string }>({
    mutationFn: async ({ comment }) => {
      const response = await api.post(`/applications/${application?.id}/unreject`, {
        comment,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      setShowReconsiderDialog(false);
      setReconsiderComment('');
    },
  });

  const startProxyMutation = useMutation<{ interviewId: number }, Error>({
    mutationFn: async () => {
      const response = await api.post(`/applications/${application?.id}/start-proxy-interview`, {});
      return response.data;
    },
    onSuccess: (data) => {
      // Navigate to the proxy interview conduct page
      onClose();
      router.push(`/interviews/${data.interviewId}/conduct`);
    },
    onError: (error) => {
      toast({
        title: 'Failed to start proxy interview',
        description: error.message || 'Please try again',
        variant: 'destructive',
      });
    },
  });

  const handleAdvance = (skipInterview = false) => {
    advanceMutation.mutate({ skipInterview });
  };

  const handleReject = (reasonCode: RejectionReasonCode) => {
    rejectMutation.mutate({ reasonCode });
  };

  const handleHold = () => {
    holdMutation.mutate();
  };

  const handleReconsider = () => {
    if (reconsiderComment.trim()) {
      unrejectMutation.mutate({ comment: reconsiderComment.trim() });
    }
  };

  // Download handlers
  const handleDownloadResume = async () => {
    try {
      const response = await api.get(`/applications/${application?.id}/resume/download`);
      window.open(response.data.url, '_blank');
    } catch (error) {
      console.error('Failed to download resume:', error);
    }
  };

  const handleDownloadReport = async () => {
    try {
      const response = await api.get(`/applications/${application?.id}/report/download`);
      window.open(response.data.url, '_blank');
    } catch (error) {
      console.error('Failed to download report:', error);
    }
  };

  const canAdvance = application && ADVANCE_VALID_STATUSES.includes(application.status);
  const canReject = application && REJECT_VALID_STATUSES.includes(application.status);
  const canHold = application && HOLD_VALID_STATUSES.includes(application.status);
  const canReconsider = application?.status === 'rejected';
  const isOnHold = application?.status === 'on_hold';

  // Get JD requirements match from facts
  const jdMatch = facts?.extractedFacts?.jd_requirements_match;
  const matchPercentage = jdMatch?.summary?.match_percentage ?? null;
  const requirements = jdMatch?.requirements ?? [];
  const metRequirements = requirements.filter(r => r.met === 'yes');
  const partialRequirements = requirements.filter(r => r.met === 'partial');
  const unmetRequirements = requirements.filter(r => r.met === 'no');

  // Get most recent position for header
  const summaryStats = facts?.extractedFacts?.summary_stats;
  const mostRecentPosition = summaryStats?.most_recent_title && summaryStats?.most_recent_employer
    ? `${summaryStats.most_recent_title} @ ${summaryStats.most_recent_employer}`
    : null;

  return (
    <>
      <Sheet open={!!application} onOpenChange={(open) => !open && onClose()}>
        <SheetContent side="right" className="w-full md:w-[65vw] max-w-none flex flex-col">
          {application && (
            <>
              <SheetHeader className="flex-shrink-0">
                <div className="flex items-center justify-between pr-8">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => hasPrev && onNavigate(applications[currentIndex - 1])}
                      disabled={!hasPrev}
                      title="Previous (←)"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      {currentIndex + 1} of {applications.length}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => hasNext && onNavigate(applications[currentIndex + 1])}
                      disabled={!hasNext}
                      title="Next (→)"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleDownloadResume}
                      title="Download Resume"
                      className="h-8 w-8"
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <span
                      className={cn(
                        'px-2 py-1 text-xs rounded-full',
                        statusColors[application.status] || 'bg-gray-100 text-gray-800'
                      )}
                    >
                      {statusLabels[application.status] || application.status}
                    </span>
                  </div>
                </div>
                <SheetTitle className="text-xl">{application.candidateName}</SheetTitle>
                <div className="text-sm text-muted-foreground">
                  {application.candidateEmail && <span>{application.candidateEmail} &bull; </span>}
                  {application.requisitionName}
                </div>
                {mostRecentPosition && (
                  <div className="text-sm font-medium text-foreground">
                    {mostRecentPosition}
                  </div>
                )}
              </SheetHeader>

              {/* Split View: Analysis Left, Resume Right (desktop only) */}
              <div className="flex-1 flex gap-4 overflow-hidden">
                {/* Left Panel - Analysis (full width on mobile, half on desktop) */}
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full md:w-1/2 flex flex-col overflow-hidden">
                  <TabsList className="w-full justify-start flex-shrink-0">
                    <TabsTrigger value="screening" className="flex-1">
                      <FileText className="h-4 w-4 mr-2" />
                      Screening
                    </TabsTrigger>
                    <TabsTrigger
                      value="interview"
                      className="flex-1"
                      disabled={!application.hasInterview}
                    >
                      <MessageSquare className="h-4 w-4 mr-2" />
                      Interview
                      {!application.hasInterview && (
                        <span className="ml-1 text-xs text-muted-foreground">(none)</span>
                      )}
                    </TabsTrigger>
                  </TabsList>

                  <SheetBody className="flex-1 overflow-auto">
                  <TabsContent value="screening" className="mt-0 h-full">
                    {/* Download Report Button */}
                    {application.hasReport && (
                      <div className="mb-4">
                        <Button variant="outline" size="sm" onClick={handleDownloadReport}>
                          <Download className="h-4 w-4 mr-2" />
                          Download Analysis Report
                        </Button>
                      </div>
                    )}

                    {factsLoading ? (
                      <div className="flex items-center justify-center h-64">
                        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
                      </div>
                    ) : facts?.extractedFacts ? (
                      <div className="space-y-6">
                        {/* JD Requirements Match */}
                        {matchPercentage !== null && (
                          <div className="p-4 rounded-lg border">
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-medium">JD Requirements Match</span>
                              <span className="text-sm font-medium">{matchPercentage}%</span>
                            </div>
                            <Progress value={matchPercentage} />
                            <div className="mt-3 space-y-3 text-sm">
                              {/* Met Requirements */}
                              {metRequirements.length > 0 && (
                                <div>
                                  <span className="text-green-600 dark:text-green-400 font-medium">
                                    Met ({metRequirements.length})
                                  </span>
                                  <div className="mt-1 space-y-1">
                                    {(expandedRequirements.met ? metRequirements : metRequirements.slice(0, 3)).map((req, i) => (
                                      <div
                                        key={i}
                                        className="px-2 py-1 text-xs bg-green-50 dark:bg-green-900/30 rounded border border-green-200 dark:border-green-800"
                                      >
                                        <div className="font-medium text-green-800 dark:text-green-200">{req.requirement}</div>
                                        {req.evidence && (
                                          <div className="text-green-600 dark:text-green-400 mt-0.5">{req.evidence}</div>
                                        )}
                                      </div>
                                    ))}
                                    {metRequirements.length > 3 && (
                                      <button
                                        onClick={() => setExpandedRequirements(prev => ({ ...prev, met: !prev.met }))}
                                        className="text-xs text-primary hover:underline cursor-pointer"
                                      >
                                        {expandedRequirements.met ? 'Show less' : `+${metRequirements.length - 3} more met`}
                                      </button>
                                    )}
                                  </div>
                                </div>
                              )}
                              {/* Partial Requirements */}
                              {partialRequirements.length > 0 && (
                                <div>
                                  <span className="text-yellow-600 dark:text-yellow-400 font-medium">
                                    Partial ({partialRequirements.length})
                                  </span>
                                  <div className="mt-1 space-y-1">
                                    {(expandedRequirements.partial ? partialRequirements : partialRequirements.slice(0, 2)).map((req, i) => (
                                      <div
                                        key={i}
                                        className="px-2 py-1 text-xs bg-yellow-50 dark:bg-yellow-900/30 rounded border border-yellow-200 dark:border-yellow-800"
                                      >
                                        <div className="font-medium text-yellow-800 dark:text-yellow-200">{req.requirement}</div>
                                        <div className="text-yellow-600 dark:text-yellow-400 mt-0.5">{req.explanation}</div>
                                      </div>
                                    ))}
                                    {partialRequirements.length > 2 && (
                                      <button
                                        onClick={() => setExpandedRequirements(prev => ({ ...prev, partial: !prev.partial }))}
                                        className="text-xs text-primary hover:underline cursor-pointer"
                                      >
                                        {expandedRequirements.partial ? 'Show less' : `+${partialRequirements.length - 2} more partial`}
                                      </button>
                                    )}
                                  </div>
                                </div>
                              )}
                              {/* Unmet Requirements */}
                              {unmetRequirements.length > 0 && (
                                <div>
                                  <span className="text-red-600 dark:text-red-400 font-medium">
                                    Not Met ({unmetRequirements.length})
                                  </span>
                                  <div className="mt-1 space-y-1">
                                    {(expandedRequirements.unmet ? unmetRequirements : unmetRequirements.slice(0, 3)).map((req, i) => (
                                      <div
                                        key={i}
                                        className="px-2 py-1 text-xs bg-red-50 dark:bg-red-900/30 rounded border border-red-200 dark:border-red-800"
                                      >
                                        <div className="font-medium text-red-800 dark:text-red-200">{req.requirement}</div>
                                        <div className="text-red-600 dark:text-red-400 mt-0.5">{req.explanation}</div>
                                      </div>
                                    ))}
                                    {unmetRequirements.length > 3 && (
                                      <button
                                        onClick={() => setExpandedRequirements(prev => ({ ...prev, unmet: !prev.unmet }))}
                                        className="text-xs text-primary hover:underline cursor-pointer"
                                      >
                                        {expandedRequirements.unmet ? 'Show less' : `+${unmetRequirements.length - 3} more not met`}
                                      </button>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Summary Stats */}
                        {summaryStats && (
                          <div className="grid grid-cols-4 gap-3">
                            <div className="p-3 rounded-lg border text-center">
                              <div className="text-xl font-bold">
                                {Math.round(summaryStats.total_experience_months / 12)}
                              </div>
                              <div className="text-xs text-muted-foreground">Yrs Total Exp</div>
                            </div>
                            <div className="p-3 rounded-lg border text-center">
                              <div className="text-xl font-bold">
                                {summaryStats.recent_5yr_employers_count ?? 0}
                              </div>
                              <div className="text-xs text-muted-foreground">Jobs (5yr)</div>
                            </div>
                            <div className="p-3 rounded-lg border text-center">
                              <div className="text-xl font-bold">
                                {Math.round(summaryStats.recent_5yr_average_tenure_months ?? 0)}
                              </div>
                              <div className="text-xs text-muted-foreground">Avg Mo/Job (5yr)</div>
                            </div>
                            <div className="p-3 rounded-lg border text-center">
                              <div className="text-xl font-bold">
                                {summaryStats.months_since_last_employment ?? 0}
                              </div>
                              <div className="text-xs text-muted-foreground">Mo Since Last</div>
                            </div>
                          </div>
                        )}

                        {/* Employment History */}
                        {facts.extractedFacts.employment_history && facts.extractedFacts.employment_history.length > 0 && (
                          <div>
                            <h3 className="font-medium flex items-center gap-2 mb-3">
                              <Briefcase className="h-4 w-4" /> Employment History
                            </h3>
                            <div className="space-y-3">
                              {facts.extractedFacts.employment_history.slice(0, 4).map((job, i) => (
                                <div key={i} className="p-3 rounded-lg border">
                                  <div className="flex items-start justify-between">
                                    <div>
                                      <div className="font-medium">{job.title}</div>
                                      <div className="text-sm text-muted-foreground">{job.employer}</div>
                                    </div>
                                    <div className="text-right text-sm text-muted-foreground">
                                      {job.start_date} - {job.is_current ? 'Present' : job.end_date}
                                      <div className="text-xs">{job.duration_months} months</div>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Licenses & Certifications */}
                        {((facts.extractedFacts.licenses && facts.extractedFacts.licenses.length > 0) ||
                          (facts.extractedFacts.certifications && facts.extractedFacts.certifications.length > 0)) && (
                          <div>
                            <h3 className="font-medium flex items-center gap-2 mb-3">
                              <Award className="h-4 w-4" /> Licenses & Certifications
                            </h3>
                            <div className="flex flex-wrap gap-2">
                              {facts.extractedFacts.licenses?.map((lic, i) => (
                                <span
                                  key={`lic-${i}`}
                                  className="px-2 py-1 text-sm bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded"
                                >
                                  {lic.type}
                                  {lic.class && ` (Class ${lic.class})`}
                                  {lic.endorsements?.length > 0 && ` - ${lic.endorsements.join(', ')}`}
                                </span>
                              ))}
                              {facts.extractedFacts.certifications?.map((cert, i) => (
                                <span
                                  key={`cert-${i}`}
                                  className="px-2 py-1 text-sm bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200 rounded"
                                >
                                  {cert.name}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Education */}
                        {facts.extractedFacts.education && facts.extractedFacts.education.length > 0 && (
                          <div>
                            <h3 className="font-medium flex items-center gap-2 mb-3">
                              <GraduationCap className="h-4 w-4" /> Education
                            </h3>
                            <div className="space-y-2">
                              {facts.extractedFacts.education.map((edu, i) => (
                                <div key={i} className="p-3 rounded-lg border">
                                  <div className="font-medium">
                                    {edu.degree} {edu.field && `in ${edu.field}`}
                                  </div>
                                  <div className="text-sm text-muted-foreground">
                                    {edu.institution}
                                    {edu.graduation_date && ` - ${edu.graduation_date}`}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* AI Observations */}
                        {(facts.pros?.length > 0 || facts.cons?.length > 0) && (
                          <div>
                            <h3 className="font-medium flex items-center gap-2 mb-3">
                              <FileText className="h-4 w-4" /> AI Observations
                            </h3>
                            <div className="grid grid-cols-2 gap-4">
                              {facts.pros?.length > 0 && (
                                <div>
                                  <h4 className="text-sm font-medium text-green-600 dark:text-green-400 flex items-center gap-1 mb-2">
                                    <ThumbsUp className="h-3 w-3" /> Strengths
                                  </h4>
                                  <ul className="space-y-2">
                                    {facts.pros.map((pro, i) => (
                                      <li key={i} className="text-sm p-2 rounded bg-green-50 dark:bg-green-900/20">
                                        <div className="font-medium">{pro.observation}</div>
                                        <div className="text-xs text-muted-foreground mt-1">{pro.evidence}</div>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {facts.cons?.length > 0 && (
                                <div>
                                  <h4 className="text-sm font-medium text-red-600 dark:text-red-400 flex items-center gap-1 mb-2">
                                    <ThumbsDown className="h-3 w-3" /> Gaps
                                  </h4>
                                  <ul className="space-y-2">
                                    {facts.cons.map((con, i) => (
                                      <li key={i} className="text-sm p-2 rounded bg-red-50 dark:bg-red-900/20">
                                        <div className="font-medium">{con.observation}</div>
                                        <div className="text-xs text-muted-foreground mt-1">{con.evidence}</div>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Suggested Questions */}
                        {facts.suggestedQuestions?.length > 0 && (
                          <div>
                            <h3 className="font-medium flex items-center gap-2 mb-3">
                              <HelpCircle className="h-4 w-4" /> Suggested Questions
                            </h3>
                            <ul className="space-y-2">
                              {facts.suggestedQuestions.map((q, i) => (
                                <li key={i} className="text-sm p-3 rounded-lg border">
                                  <div className="font-medium">{q.question}</div>
                                  <div className="text-xs text-muted-foreground mt-1">
                                    <span className="font-medium">Topic:</span> {q.topic} &bull;{' '}
                                    <span className="font-medium">Reason:</span> {q.reason}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Extraction Notes */}
                        {facts.extractionNotes && (
                          <div className="p-3 rounded-lg border border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/20">
                            <div className="flex items-start gap-2">
                              <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                              <div>
                                <div className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                                  Extraction Notes
                                </div>
                                <div className="text-sm text-yellow-700 dark:text-yellow-300">
                                  {facts.extractionNotes}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                        <FileText className="h-12 w-12 mb-4 opacity-50" />
                        <p>No extracted facts available</p>
                        <p className="text-sm">Facts will appear once the application is processed</p>
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="interview" className="mt-0 h-full">
                    {application.hasInterview && interviewData ? (
                      <div className="space-y-6">
                        {/* Download Interview Report */}
                        {application.hasReport && (
                          <div className="mb-4">
                            <Button variant="outline" size="sm" onClick={handleDownloadReport}>
                              <Download className="h-4 w-4 mr-2" />
                              Download Interview Report
                            </Button>
                          </div>
                        )}

                        {/* Interview Meta */}
                        <div className="p-4 rounded-lg border">
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="font-medium">AI Interview</div>
                              <div className="text-sm text-muted-foreground">
                                {interviewData.interview.interviewType} &bull; {interviewData.interview.messageCount} messages
                              </div>
                            </div>
                            <div className="text-right text-sm text-muted-foreground">
                              {interviewData.interview.completedAt
                                ? `Completed ${formatRelativeTime(interviewData.interview.completedAt)}`
                                : interviewData.interview.status}
                            </div>
                          </div>
                        </div>

                        {/* Evaluation Summary */}
                        {interviewData.evaluation && (
                          <>
                            {interviewData.evaluation.summary && (
                              <div>
                                <h3 className="font-medium mb-2">Summary</h3>
                                <Markdown className="text-sm text-muted-foreground">
                                  {interviewData.evaluation.summary}
                                </Markdown>
                              </div>
                            )}

                            {interviewData.evaluation.interviewHighlights?.length > 0 && (
                              <div>
                                <h3 className="font-medium flex items-center gap-2 mb-3">
                                  <ThumbsUp className="h-4 w-4" /> Key Highlights
                                </h3>
                                <ul className="space-y-2">
                                  {interviewData.evaluation.interviewHighlights.map((h, i) => (
                                    <li key={i} className="text-sm p-2 rounded bg-green-50 dark:bg-green-900/20">
                                      {h}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {interviewData.evaluation.nextInterviewFocus?.length > 0 && (
                              <div>
                                <h3 className="font-medium flex items-center gap-2 mb-3">
                                  <HelpCircle className="h-4 w-4" /> Areas for Live Interview
                                </h3>
                                <ul className="space-y-2">
                                  {interviewData.evaluation.nextInterviewFocus.map((f, i) => (
                                    <li key={i} className="text-sm p-2 rounded bg-blue-50 dark:bg-blue-900/20">
                                      {f}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </>
                        )}

                        {!interviewData.evaluation && (
                          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                            <p>Interview evaluation pending</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                        <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
                        <p>No interview conducted yet</p>
                      </div>
                    )}
                  </TabsContent>
                  </SheetBody>
                </Tabs>

                {/* Right Panel - Resume PDF (hidden on mobile) */}
                <div className="hidden md:flex md:w-1/2 flex-col border rounded-lg overflow-hidden bg-muted/30">
                  <div className="flex items-center justify-between px-3 py-2 border-b bg-background">
                    <span className="text-sm font-medium">Resume</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleDownloadResume}
                      title="Open in new tab"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="flex-1 overflow-hidden">
                    {resumeUrl ? (
                      <iframe
                        src={resumeUrl}
                        className="w-full h-full border-0"
                        title="Resume PDF"
                      />
                    ) : (
                      <div className="flex items-center justify-center h-full text-muted-foreground">
                        <div className="text-center">
                          <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">Loading resume...</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <SheetFooter className="flex-col sm:flex-row gap-2 flex-shrink-0 border-t pt-4">
                {isOnHold ? (
                  <Button onClick={() => handleAdvance()} disabled={advanceMutation.isPending}>
                    <Clock className="h-4 w-4 mr-2" />
                    {advanceMutation.isPending ? 'Removing from Hold...' : 'Remove from Hold'}
                  </Button>
                ) : (
                  <>
                    {canHold && (
                      <Button
                        variant="outline"
                        onClick={handleHold}
                        disabled={holdMutation.isPending}
                      >
                        <Clock className="h-4 w-4 mr-2" />
                        {holdMutation.isPending ? 'Holding...' : 'Hold'}
                      </Button>
                    )}
                    {canReject && (
                      <Button
                        variant="destructive"
                        onClick={() => setShowRejectDialog(true)}
                      >
                        <XCircle className="h-4 w-4 mr-2" />
                        Reject
                      </Button>
                    )}
                    {canAdvance && application.status === 'ready_for_review' && (
                      <>
                        <Button
                          onClick={() => setShowInterviewModal(true)}
                        >
                          <Send className="h-4 w-4 mr-2" />
                          Self Interview
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => startProxyMutation.mutate()}
                          disabled={startProxyMutation.isPending}
                        >
                          {startProxyMutation.isPending ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          ) : (
                            <Phone className="h-4 w-4 mr-2" />
                          )}
                          Proxy Interview
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => handleAdvance(true)}
                          disabled={advanceMutation.isPending}
                        >
                          <ExternalLink className="h-4 w-4 mr-2" />
                          Skip AI
                        </Button>
                      </>
                    )}
                    {canAdvance && application.status === 'interview_ready_for_review' && (
                      <Button
                        onClick={() => handleAdvance(false)}
                        disabled={advanceMutation.isPending}
                      >
                        <CheckCircle className="h-4 w-4 mr-2" />
                        {advanceMutation.isPending ? 'Advancing...' : 'Advance'}
                      </Button>
                    )}
                    {canReconsider && (
                      <Button
                        variant="outline"
                        onClick={() => setShowReconsiderDialog(true)}
                      >
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Reconsider
                      </Button>
                    )}
                  </>
                )}
              </SheetFooter>
            </>
          )}
        </SheetContent>
      </Sheet>

      <RejectReasonSelector
        open={showRejectDialog}
        onOpenChange={setShowRejectDialog}
        onConfirm={handleReject}
        isLoading={rejectMutation.isPending}
        candidateName={application?.candidateName}
      />

      <SendInterviewModal
        application={application}
        open={showInterviewModal}
        onOpenChange={setShowInterviewModal}
        onSuccess={() => {
          // Navigate to next application or close drawer after sending interview
          if (hasNext) {
            onNavigate(applications[currentIndex + 1]);
          } else {
            onClose();
          }
        }}
      />

      {/* Reconsider Dialog */}
      <Dialog open={showReconsiderDialog} onOpenChange={(open) => {
        setShowReconsiderDialog(open);
        if (!open) setReconsiderComment('');
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reconsider Application</DialogTitle>
            <DialogDescription className="space-y-2">
              <p>
                This will move <strong>{application?.candidateName}</strong> back to the review queue.
              </p>
              <p className="text-amber-600 dark:text-amber-400 font-medium">
                Note: This change will NOT sync to Workday. The candidate will remain rejected in Workday.
              </p>
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <label className="text-sm font-medium" htmlFor="reconsider-comment">
              Reason for reconsideration (required)
            </label>
            <Textarea
              id="reconsider-comment"
              placeholder="e.g., Rejected in error - meant different candidate"
              value={reconsiderComment}
              onChange={(e) => setReconsiderComment(e.target.value)}
              className="mt-2"
              rows={3}
            />
            <p className="text-xs text-muted-foreground mt-2">
              This comment will be stored in the audit trail.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowReconsiderDialog(false);
                setReconsiderComment('');
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleReconsider}
              disabled={!reconsiderComment.trim() || unrejectMutation.isPending}
            >
              {unrejectMutation.isPending ? 'Processing...' : 'Reconsider'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
