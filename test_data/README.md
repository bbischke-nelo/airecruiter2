# Test Data

This directory contains sample application and resume files for testing.

## Files

- `REGIO004114-application.json` - Sample application data (Janine Elliott for Regional Sales Director)
- `REGIO004114-resume.docx` - Sample resume document

## Usage

Run the seed script to load this data into the database:

```bash
# From project root, with venv activated
python scripts/seed_test_data.py

# Or specify files explicitly
python scripts/seed_test_data.py test_data/REGIO004114-application.json test_data/REGIO004114-resume.docx
```

The script will:
1. Create the requisition (REGIO004114 - Regional Sales Director)
2. Create the application (Janine Elliott)
3. Upload the resume to S3 (or store local path if S3 unavailable)
4. Queue an analysis job

## Adding More Test Data

Add additional `.json` and `.docx` pairs following the naming pattern:
- `{REQUISITION_ID}-application.json`
- `{REQUISITION_ID}-resume.docx`
