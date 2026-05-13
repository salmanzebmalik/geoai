# GeoAI Architecture

## 1. High-Level Architecture

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

## 2. Current System Flow

```text
1. User selects an area on the frontend map.
2. Frontend sends the selected bounding-box coordinates to the backend.
3. Backend validates the coordinates.
4. Backend creates a new query record in the database.
5. Backend generates or prepares an image for the selected area.
6. Backend sends the image to the segmentation logic.
7. Segmentation logic returns a mask/predictions (still need to finalize).
8. Backend stores the prediction result in Supabase.
9. Backend returns the result reference and prediction metadata to the frontend.
10. Frontend displays the image, segmentation mask, and prediction summary.
11. User can later fetch previous results from the backend.
```

---

## 3. Current Technical Components

### 3.1 Frontend

The frontend is responsible for:

```text
- Displaying the map
- Allowing the user to draw/select a bounding box
- Sending the selected coordinates to the backend
- Displaying returned prediction results
- Displaying image and mask overlays
- Showing previous query history
```

The frontend should only communicate with the backend API.

```text
Frontend → FastAPI Backend
```

The frontend should not directly access:

```text
- Supabase database
- Database credentials
- ML model
- Backend internal services
```

---

### 3.2 FastAPI Backend

The backend is the central coordination layer.

It is responsible for:

```text
- Receiving API requests from frontend
- Validating bounding-box coordinates
- Creating and updating query records
- Communicating with Supabase
- Preparing image data
- Calling the segmentation logic
- Serving static image and mask files
- Returning structured results to frontend
```

Current backend responsibilities are organized into separate files:

```text
main.py
    FastAPI application setup, CORS, static file serving, route registration

routes.py
    API endpoint definitions

schemas.py
    API request and response schema definitions

services.py
    Core processing logic, dummy image generation, dummy segmentation logic

database.py
    Supabase/PostgreSQL database connection

db_models.py
    Database table model definitions
```

---

### 3.3 Supabase PostgreSQL Database

Supabase PostgreSQL is used as the persistent storage layer.

The database stores:

```text
- Query ID
- Bounding-box coordinates
- Processing status
- Image URL
- Image metadata
- Prediction result
- Summary
- Creation timestamp
```

The backend communicates with Supabase using SQLModel/SQLAlchemy.

```text
FastAPI Backend → SQLModel/SQLAlchemy → Supabase PostgreSQL
```

The database allows previous queries to remain available even after the backend server restarts.

---

### 3.4 Image Layer

The image layer is responsible for preparing an image for the selected geographic area.

Current prototype behavior:

```text
- Backend generates a dummy satellite-like image.
- Image is saved in static/images.
- Backend returns an image URL to the frontend.
```

Future behavior:

```text
- Backend receives bounding-box coordinates.
- Data service fetches or crops a real satellite image for the selected area.
- Image is saved locally or in cloud storage.
- Image URL is stored in the database.
- Image is passed to the ML model for inference.
```

This layer will later be owned jointly by the backend and data teams.

---

### 3.5 ML Inference Layer

The ML inference layer is responsible for semantic segmentation.

Current prototype behavior:

```text
- Backend generates a dummy segmentation mask.
- Backend returns fixed class coverage values.
- No real ML model is connected yet.
```

Future behavior:

```text
- Backend passes the satellite image to the ML module.
- ML model performs semantic segmentation.
- Model returns a segmentation mask.
- Model or backend calculates class coverage percentages.
- Backend saves the mask and stores the prediction result.
```

The frontend should not need to change when the dummy ML logic is replaced with a real model, as long as the API contract remains stable.

---

## 4. API Flow Overview

The backend currently exposes three main API flows.

---

### 4.1 Create New Segmentation Prediction

```http
POST /api/segmentation/predict
```

Purpose:

```text
Creates a new segmentation prediction for a selected geographic area.
```

Technical flow:

```text
Frontend sends selected map coordinates.
Backend validates the coordinates.
Backend creates a new database record.
Backend prepares image data.
Backend runs segmentation logic.
Backend stores prediction output.
Backend returns prediction result to frontend.
```

This is the main endpoint used when a user draws a new area on the map.

---

### 4.2 Fetch All Previous Segmentation Results

```http
GET /api/segmentation/results
```

Purpose:

```text
Returns all previously executed segmentation queries.
```

Technical flow:

```text
Frontend requests query history.
Backend reads stored query records from Supabase.
Backend returns a list of previous results.
Frontend displays the history list.
```

This endpoint is used for the query history panel.

---

### 4.3 Fetch One Previous Segmentation Result

```http
GET /api/segmentation/results/{query_id}
```

Purpose:

```text
Returns the full result for one previously executed segmentation query.
```

Technical flow:

```text
Frontend sends selected query ID.
Backend searches the database for that query.
Backend reconstructs the stored result.
Backend returns the full result to frontend.
Frontend displays the selected result.
```

This endpoint is used when the user clicks a previous query.

---

## 5. Static File Flow

The backend serves generated images and masks through FastAPI static file serving.

Current static folder structure:

```text
static/
    images/
        generated satellite-like images

    masks/
        generated segmentation mask images
```

Technical flow:

```text
Backend generates image or mask file.
File is saved under static directory.
FastAPI exposes the file through /static URL.
Frontend uses the returned file URL to display the image or mask.
```

Current examples of static URL patterns:

```text
/static/images/{query_id}.png
/static/masks/{query_id}_mask.png
```

---

## 6. Database Flow

The database flow is handled through the backend service layer.

```text
API request received
   ↓
Service creates or updates database object
   ↓
SQLModel session saves object
   ↓
Supabase stores row
   ↓
Backend returns result
```

For creating a new prediction:

```text
1. A database row is created with status = processing.
2. Image and segmentation processing run.
3. The database row is updated with status = completed.
4. Image URL, mask URL, prediction result, and summary are saved.
```

This makes the design ready for longer-running ML tasks in the future.

---

## 7. DevOps

### Containerization

```text
Frontend Container
   ↓
Backend Container
   ↓
ML Service Container
   ↓
Supabase PostgreSQL
```

### Kubernetes

```text
Kubernetes Cluster
│
├── Frontend Deployment
├── Backend Deployment
├── ML Service Deployment
├── Backend Service
├── Frontend Service
├── ML Service
├── Ingress
└── Secrets / ConfigMaps
```
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