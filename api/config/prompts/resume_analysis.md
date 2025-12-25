### Instructions
Analyze resume and application questions for the **${requisitionTitle}** position.
Job Description: ${requisitionBriefDescription}

Focus on: retention predictors, safety experience (if role is safety-sensitive), role fit.
Use application date ${applicationDate} as reference for all time calculations.
Applicant ID: ${candidateId}

**Format:** Time in decimal years, booleans as 1/0, rates per 1000 words.
**Constraint:** Evaluate only job-relevant qualifications. Never consider protected characteristics.

### Application Data
${candidate}

### Required Output Fields

**1. general.jobAnalysis:**
- isSafetySensitive (1/0) + safetySensitiveRationale
- requiresEquipmentOperation (1/0) + equipmentOperationRationale
- currentJobRelevance (0/0.25/0.5/0.75/1: none→identical) + currentJobRelevanceRationale

**2. general.riskRating:** 0.0 (lowest risk) to 1.0 (highest risk)
Based on: stability, safety experience, role fit, education. Missing info increases risk.

**3. general.metrics.employment:**
- currentRoleYears, employers5yr, totalExperienceYears, avgTenure5yr
- gapYears5yr (include gap between most recent job end and application date)

**4. general.metrics.roleExperience:**
- safetyRoleYears, avgSafetyTenure, equipmentYears
- currentSafety (1/0), currentEquipment (1/0)

**5. general.metrics.education:** postSecondaryYears

**6. general.metrics.language:** safetyTermsPer1000, productivityTermsPer1000

**7. general.metrics.certifications:**
- cdl: {years, class, hasHazmat, hasTanker, hasLcv}
  - class must be one of: "A", "B", "C", "N/A" (use "N/A" if candidate has no CDL)
- safetyCertCount, professionalCertCount

**8. general.assessment:**
- pros: [{category, description, evidence}] - cite specific resume/application content
- cons: [{category, description, evidence}] - cite specific resume/application content
- keyRisk: Primary retention/safety concern

**9. general.interviewQuestions:** [{category: "pro"|"con"|"risk", linkedItem, questions[]}]

**10. general.qualifiers:** completeHistory (1/0 - full 5yr history provided)

**11. general.metadata:** analysisDate, applicantId, sourceFile

### Output Requirements
- Return valid JSON exactly like the example below
- All fields are REQUIRED - populate every field
- Calculate metrics precisely from resume content
- Use the exact field names and data types shown in the example

### Example Output Format
```json
${example}
```
