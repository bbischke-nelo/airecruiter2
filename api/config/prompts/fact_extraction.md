## Resume Fact Extraction

Extract factual information from this resume for the **{requisition_title}** position.
Use application date {application_date} as reference for time calculations.
Applicant ID: {candidate_id}

**CRITICAL CONSTRAINTS:**
- Extract ONLY facts explicitly stated in the resume
- DO NOT score, rank, rate, or assess the candidate
- DO NOT infer skills or experience not explicitly mentioned
- DO NOT make recommendations or judgments
- Use null for any field not explicitly stated

### Job Description (for context only - do not score against it)
{job_description}

### Resume/Application Data
{resume}

### Required Output (JSON)

Return this exact structure:

```json
{
  "extraction_version": "2.0",
  "extracted_at": "<ISO timestamp>",

  "employment_history": [
    {
      "employer": "<company name>",
      "title": "<job title>",
      "start_date": "<YYYY-MM or null>",
      "end_date": "<YYYY-MM or null if current>",
      "is_current": true/false,
      "duration_months": <calculated number>,
      "location": "<city, state or null>",
      "responsibilities": ["<as stated>"],
      "industry": "<if discernible from company/role>"
    }
  ],

  "skills": {
    "technical": ["<explicitly listed skills>"],
    "software": ["<systems, tools, platforms mentioned>"],
    "industry_specific": ["<domain skills: CDL, forklift, TMS, etc>"],
    "certifications_mentioned_in_skills": ["<certs listed in skills section>"]
  },

  "certifications": [
    {
      "name": "<certification name>",
      "issuer": "<issuing body or null>",
      "date_obtained": "<YYYY-MM or null>",
      "expiration": "<YYYY-MM or null>",
      "details": "<class, endorsements, etc or null>"
    }
  ],

  "licenses": [
    {
      "type": "<CDL-A, CDL-B, forklift, etc>",
      "class": "<A, B, C, or null>",
      "endorsements": ["<Hazmat, Tanker, Doubles, etc>"],
      "state": "<issuing state or null>",
      "expiration": "<YYYY-MM or null>"
    }
  ],

  "education": [
    {
      "institution": "<school name>",
      "degree": "<degree type or null>",
      "field": "<field of study or null>",
      "graduation_date": "<YYYY-MM or null>",
      "gpa": "<if stated, else null>"
    }
  ],

  "logistics": {
    "location_stated": "<city, state or null>",
    "willing_to_relocate": "<yes/no/not stated>",
    "remote_preference": "<remote/hybrid/onsite/not stated>",
    "travel_willingness": "<percentage or description or null>"
  },

  "timeline": [
    {
      "type": "employment|education|gap",
      "entity": "<employer or school name>",
      "from": "<YYYY-MM>",
      "to": "<YYYY-MM or null>",
      "duration_months": <number>
    }
  ],

  "summary_stats": {
    "total_experience_months": <calculated>,
    "employers_count": <number>,
    "average_tenure_months": <calculated>,
    "most_recent_employer": "<name>",
    "most_recent_title": "<title>",
    "years_since_last_employment": <if gap to present>
  },

  "jd_keyword_matches": {
    "found": ["<keywords from JD found in resume>"],
    "not_found": ["<keywords from JD not found in resume>"]
  },

  "observations": {
    "pros": [
      {
        "category": "<experience|skills|certifications|education|other>",
        "observation": "<factual observation tied to JD requirement>",
        "evidence": "<specific quote or fact from resume>"
      }
    ],
    "cons": [
      {
        "category": "<experience|skills|certifications|education|other>",
        "observation": "<factual gap relative to JD requirement>",
        "evidence": "<what's missing or unclear>"
      }
    ],
    "suggested_questions": [
      {
        "topic": "<what to clarify>",
        "question": "<specific question to ask>",
        "reason": "<why this needs clarification based on resume>"
      }
    ]
  },

  "extraction_notes": "<any parsing issues, unclear data, or flags>"
}
```

### DO NOT CONSIDER (Off-Limits for Pros/Cons/Questions):

**Protected Characteristics (Federal Law):**
- Race or color
- National origin or ancestry
- Sex, gender, or gender identity
- Sexual orientation
- Religion or religious practices
- Age (40+) - do not infer from graduation dates
- Disability (physical or mental)
- Genetic information or family medical history
- Pregnancy, childbirth, or related conditions
- Veteran or military status
- Citizenship status (beyond work authorization)

**Protected Activities & Status:**
- Union membership or activity
- Workers' compensation history
- Prior lawsuits against employers
- Whistleblower activity
- FMLA leave usage

**Proxy Variables (Handle With Care):**
- Employment gaps - Present timeline factually, don't characterize or penalize
- Number of jobs - Present count, don't label as "job hopper"
- Graduation dates - Don't use to calculate age
- Name patterns - Never consider

**Actually Subjective (Avoid):**
- "Culture fit" - Means nothing, often mask for bias
- "Gut feeling" - Not defensible
- "Attitude" - Too vague unless specific behavioral example

### DO FOCUS ON (For Pros/Cons/Questions):
- Specific skills/certifications required in JD vs what's in resume
- Years of relevant experience vs JD minimum
- Specific tools/systems mentioned in JD vs resume
- Licenses required vs licenses held
- Concrete accomplishments relevant to the role
- Gaps in information that need clarification (not judgment)

### Rules:
1. Calculate duration_months from dates when possible
2. List timeline entries in reverse chronological order
3. For JD keyword matching, extract key requirements from JD and check resume
4. If resume is unparseable (image, corrupted), return minimal structure with extraction_notes explaining the issue
5. Do not include personal information beyond what's job-relevant (no age, race, gender inference)
6. Pros/cons must tie directly to a JD requirement - not general observations
7. Suggested questions should clarify facts, not probe character or personality
