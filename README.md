
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

## Command-line client

The `geoai` command exposes the segmentation API for scripts and terminal use. After
installing the project environment, run it from the repository root with:

```bash
uv run geoai --help
```

It targets the development backend at
`http://127.0.0.1:8013/api/segmentation` by default. Point it at another backend
with `--api-url` or the `GEOAI_API_URL` environment variable:

```bash
export GEOAI_API_URL=http://127.0.0.1:8013/api/segmentation
```

Run a tree prediction:

```bash
uv run geoai predict \
  --bbox 7.6179951 51.9651518 7.6233891 51.966658 \
  --source-type ortho \
  --model-type tree
```

Run a zero-shot prediction with multiple terms:

```bash
uv run geoai predict \
  --bbox 7.6179951 51.9651518 7.6233891 51.966658 \
  --source-type ortho \
  --model-type zeroshot \
  --model-variant sam2.1_hiera_tiny \
  --keyword building \
  --keyword car
```

Both `sam2.1_hiera_large` (the default) and `sam2.1_hiera_tiny` are supported.
Sentinel predictions can use the same imagery filters as the frontend:

```bash
uv run geoai predict \
  --bbox 7.6179951 51.9651518 7.6233891 51.966658 \
  --source-type sentinel \
  --model-type tree_satlas \
  --date-from 2023-06-01 \
  --date-to 2023-06-30 \
  --max-cloud-cover 15
```

Estimate the raster workload before starting a prediction:

```bash
uv run geoai estimate \
  --bbox 7.6179951 51.9651518 7.6233891 51.966658 \
  --source-type sentinel \
  --model-type tree_satlas
```

Inspect and download results:

```bash
uv run geoai results list
uv run geoai results show QUERY_ID
uv run geoai results download QUERY_ID -o prediction.geojson
uv run geoai results delete QUERY_ID
```

Create an export for an existing prediction:

```bash
uv run geoai exports create QUERY_ID \
  --overlay-color '#ff0000' \
  --overlay-opacity 0.45 \
  --mask-tiff
```

Prediction and export can also be executed in one request:

```bash
uv run geoai predict-export \
  --bbox 7.6179951 51.9651518 7.6233891 51.966658 \
  --source-type ortho \
  --model-type tree \
  --mask-tiff
```

List and download export artifacts:

```bash
uv run geoai exports list --query-id QUERY_ID
uv run geoai exports show EXPORT_ID
uv run geoai exports download EXPORT_ID zip -o annotations.zip
```

Use the command-specific `--help` output for vector formats, CRS selection,
feature filters, TIFF layers, and other export options. API errors are written to
stderr and result in a non-zero exit status, making the command suitable for shell
scripts.

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
