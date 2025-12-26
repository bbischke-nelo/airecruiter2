## Interview Summary

Summarize this interview transcript factually. DO NOT score, rate, or recommend.

**Candidate:** {candidate_name}
**Position:** {requisition_title}
**Interview Date:** {interview_date}

### Transcript
{transcript}

### Required Output (JSON)

```json
{
  "summary_version": "2.0",
  "summarized_at": "<ISO timestamp>",

  "summary": "<2-3 paragraph factual summary of what the candidate discussed>",

  "highlights": [
    {
      "topic": "<topic discussed>",
      "observation": "<factual summary of their response>",
      "quote": "<relevant direct quote if available>"
    }
  ],

  "experience_discussed": [
    {
      "employer": "<company mentioned>",
      "role": "<role discussed>",
      "context": "<what they said about this experience>"
    }
  ],

  "skills_mentioned": ["<skills candidate claimed during interview>"],

  "topics_covered": ["<list of main topics discussed>"],

  "questions_candidate_asked": ["<questions they asked us>"],

  "candidate_preferences": {
    "availability": "<what they said about start date, schedule>",
    "location": "<what they said about location, commute, relocation>",
    "compensation": "<what they said about salary expectations, if discussed>",
    "remote_preference": "<what they said about remote/onsite>"
  },

  "follow_up_areas": [
    {
      "topic": "<area needing follow-up>",
      "reason": "<why this needs follow-up>",
      "suggested_question": "<question for live interview>"
    }
  ],

  "transcript_quality": {
    "completeness": "complete|partial|poor",
    "notes": "<any technical issues, interruptions, unclear sections>"
  }
}
```

### Rules:
1. Summarize ONLY what the candidate actually said
2. DO NOT evaluate, score, or assess their responses
3. DO NOT make recommendations (interview, review, decline)
4. DO NOT judge authenticity, character, or fit
5. Use direct quotes where relevant
6. Note any factual claims that could be verified (dates, numbers, companies)
7. If transcript is incomplete or unclear, note in transcript_quality
