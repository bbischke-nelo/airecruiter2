"""Job processors for the processing pipeline.

The processors implement the candidate processing pipeline:

1. SyncProcessor - Syncs requisitions/applications from Workday
2. DownloadResumeProcessor - Downloads resume from Workday
3. ExtractFactsProcessor - AI fact extraction from resume via Claude
4. SendInterviewProcessor - Sends interview invitations via SES
5. EvaluateProcessor - AI interview evaluation via Claude
6. GenerateReportProcessor - Generates PDF candidate reports
7. UploadReportProcessor - Uploads reports to Workday
8. UpdateWorkdayStageProcessor - Updates candidate stage in Workday
"""

from .base import BaseProcessor
from .sync import SyncProcessor
from .download_resume import DownloadResumeProcessor
from .extract_facts import ExtractFactsProcessor
from .send_interview import SendInterviewProcessor
from .evaluate import EvaluateProcessor
from .generate_report import GenerateReportProcessor
from .upload_report import UploadReportProcessor
from .update_workday_stage import UpdateWorkdayStageProcessor

__all__ = [
    "BaseProcessor",
    "SyncProcessor",
    "DownloadResumeProcessor",
    "ExtractFactsProcessor",
    "SendInterviewProcessor",
    "EvaluateProcessor",
    "GenerateReportProcessor",
    "UploadReportProcessor",
    "UpdateWorkdayStageProcessor",
]
