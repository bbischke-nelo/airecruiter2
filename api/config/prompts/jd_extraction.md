## Job Description Requirements Extraction

Extract the factual requirements from this job description.

**Position:** {requisition_title}
**Job Description:**
{requisition_description}

### Required Output (JSON)

```json
{
  "extraction_version": "1.0",

  "required_qualifications": {
    "licenses": ["<required licenses: CDL-A, etc>"],
    "certifications": ["<required certs>"],
    "education": "<minimum education if stated>",
    "experience_years": "<minimum years if stated>",
    "skills_required": ["<explicitly required skills>"]
  },

  "preferred_qualifications": {
    "licenses": ["<preferred licenses>"],
    "certifications": ["<preferred certs>"],
    "education": "<preferred education>",
    "experience_years": "<preferred years>",
    "skills_preferred": ["<nice-to-have skills>"]
  },

  "logistics": {
    "location": "<job location>",
    "remote_option": "<yes/no/hybrid>",
    "travel_required": "<percentage or description>",
    "schedule": "<shift, hours if stated>"
  },

  "keywords": ["<key terms for matching>"],

  "role_context": {
    "department": "<department if mentioned>",
    "reports_to": "<reporting structure if mentioned>",
    "team_size": "<if mentioned>",
    "responsibilities": ["<key responsibilities>"]
  }
}
```

### Rules:
1. Distinguish between REQUIRED and PREFERRED qualifications
2. Extract only what is explicitly stated
3. Do not infer or expand requirements
4. Use null for any field not explicitly stated
5. Keywords should include specific terms useful for resume matching
