
## High-Level Architecture

```text
Frontend (Vue + Veutify)
   ↓
FastAPI Backend
   ↓
Supabase PostgreSQL
   ↓
Image Processing Layer
   ↓
ML Inference Layer
   ↓
FastAPI Backend
   ↓
Frontend
```

The frontend does not communicate directly with the database or ML model. All communication goes through the FastAPI backend.

---

## Git Workflow

We use `develop` as the main integration branch and keep `main` stable.

### Branch Flow

```text
feature branch → develop → main

Rules:

- Do not push directly to main.
- Create all new work branches from develop.
- Merge feature branches into develop using Pull Requests.
- Merge develop into main only after the integrated code is tested and stable.
- Do not commit secrets or local files.
```
