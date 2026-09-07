# Deployment Guide: Cloud Hosting (Supabase + Render/Railway + Vercel)

This guide walks you through deploying the complete multi-tenant RAG stack for **free** on:
- **Database**: [Supabase](https://supabase.com) (Managed PostgreSQL with pre-installed `pgvector`)
- **Backend**: [Render](https://render.com) or [Railway](https://railway.app) (Dockerized FastAPI with Tesseract OCR & CPU PyTorch)
- **Frontend**: [Vercel](https://vercel.com) (React 18 + Vite SPA)

---

## Architecture Overview

```
[User Browser]
      │
      ▼
┌──────────────┐         API Calls (SSE)         ┌─────────────────────────┐
│    Vercel    │ ──────────────────────────────▶ │     Render / Railway    │
│  (Frontend)  │                                 │    (FastAPI + Docker)   │
└──────────────┘                                 └────────────┬────────────┘
                                                              │
                                            PostgreSQL (pgvector)
                                                              ▼
                                                 ┌─────────────────────────┐
                                                 │        Supabase         │
                                                 │   (PostgreSQL Database) │
                                                 └─────────────────────────┘
```

---

## Step 1: Provision Database on Supabase

1. Sign in to [Supabase](https://supabase.com) and click **New project**.
2. Set a Project Name (e.g., `weave-rag`) and generate a secure **Database Password**. Note down this password.
3. Choose a region closest to your backend (e.g., `East US` if deploying on Render US East).
4. Enable `pgvector` (usually auto-installed by the app, but you can verify):
   - Open **SQL Editor** in Supabase and run:
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     ```
5. Get your Connection String:
   - Go to **Project Settings** -> **Database**.
   - Under **Connection string**, select **URI**.
   - Copy the string. It will look like:
     ```
     postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
     ```
   *(Replace `[YOUR-PASSWORD]` with your real password).*

> **Note:** The backend automatically executes schema DDL migrations (`collections`, `documents`, `chunks`, `csv_tables`, and HNSW vector indices) on first boot. No manual table setup is required.

---

## Step 2: Deploy Backend to Render (or Railway)

### Option A: Render (Recommended for Free Tier)

1. Sign in to [Render](https://render.com) and click **New +** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure the service settings:
   - **Name**: `weave-api` (or similar)
   - **Root Directory**: `backend`
   - **Language / Environment**: **Docker** *(Render will automatically detect `backend/Dockerfile`)*
   - **Instance Type**: Free or Starter
4. Add **Environment Variables** under the Environment tab:
   | Variable | Value | Description |
   | :--- | :--- | :--- |
   | `DATABASE_URL` | `postgresql://postgres:pass@db.ref.supabase.co:5432/postgres` | Your Supabase connection URI |
   | `GEMINI_API_KEY` | `AIzaSy...` | Your Google Gemini API Key |
   | `GEMINI_MODEL_NAME` | `gemini-3.6-flash` | Primary LLM model |
   | `GROQ_API_KEY` | `gsk_...` *(Optional)* | Groq key for automatic 429 quota fallback |
   | `GROQ_MODEL_NAME` | `openai/gpt-oss-120b` | Fallback LLM model |
   | `CORS_ORIGINS` | `*` *(or your Vercel URL once deployed)* | Allowed CORS origins |
   | `APP_ENV` | `production` | Production mode |
5. Click **Create Web Service**.
6. Wait for the build to finish. Once live, copy your service URL (e.g. `https://weave-api.onrender.com`).

---

## Step 3: Deploy Frontend to Vercel

1. Sign in to [Vercel](https://vercel.com) and click **Add New...** -> **Project**.
2. Import your GitHub repository.
3. In **Project Configuration**:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click **Edit** and choose `frontend`.
4. In **Environment Variables**, add:
   | Variable | Value |
   | :--- | :--- |
   | `VITE_API_URL` | `https://weave-api.onrender.com` *(your backend URL from Step 2)* |
5. Click **Deploy**.
6. Once deployed, test the live URL (e.g. `https://weave-frontend.vercel.app`).

*(Optional security polish: In Render, update `CORS_ORIGINS` from `*` to `https://weave-frontend.vercel.app`)*

---

## Step 4: Verification & Smoke Test

1. **Check Backend Health**:
   - Visit `https://weave-api.onrender.com/health` in your browser.
   - Expected response:
     ```json
     {
       "status": "healthy",
       "database": "connected",
       "pgvector": "available",
       "embedding_model": "all-MiniLM-L6-v2",
       "llm_primary": "gemini-3.6-flash",
       "llm_fallback": "openai/gpt-oss-120b"
     }
     ```
2. **Open Frontend**:
   - Open your Vercel URL.
   - Verify the default collection loads.
   - Upload a sample PDF or CSV (e.g. `test_financial_benchmark.csv`).
   - Ask a semantic question or SQL question (e.g. *"What is the total revenue?"*).
   - Check that SSE streaming and citations drawer work as expected.
