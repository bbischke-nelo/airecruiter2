"""Job processors for the processing pipeline.

The 6 processors implement the candidate processing pipeline:

1. SyncProcessor - Syncs requisitions/applications from Workday
2. AnalyzeProcessor - AI resume analysis via Claude
3. SendInterviewProcessor - Sends interview invitations via SES
4. EvaluateProcessor - AI interview evaluation via Claude
5. GenerateReportProcessor - Generates PDF candidate reports
6. UploadReportProcessor - Uploads reports to Workday
"""

from .base import BaseProcessor
from .sync import SyncProcessor
from .analyze import AnalyzeProcessor
from .send_interview import SendInterviewProcessor
from .evaluate import EvaluateProcessor
from .generate_report import GenerateReportProcessor
from .upload_report import UploadReportProcessor

__all__ = [
    "BaseProcessor",
    "SyncProcessor",
    "AnalyzeProcessor",
    "SendInterviewProcessor",
    "EvaluateProcessor",
    "GenerateReportProcessor",
    "UploadReportProcessor",
]
