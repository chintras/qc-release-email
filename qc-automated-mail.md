# QC Automated Release Email — Techoil BVT2

## Overview

Automatically sends a formatted QC Release Notes email every weekday at **9:30 AM IST**
to the team group email. Runs entirely in **Azure DevOps cloud** — machine does not need to be on.

---

## Configuration

| Property | Value |
|---|---|
| ADO Organization | inatech |
| ADO Project | Techoil |
| Pipeline Folder | `\Inatech\Techoil New Pipelines\Techoil-3.3.0` |
| Environment tracked | BVT2 |
| QC URL | https://qc1.techoil.com/ |
| Version label | 3.3.0 (Develop) |
| Schedule | 9:30 AM IST, Monday–Friday |
| One Time Script | Always N/A (static row, not automated) |

---

## Architecture

```
Azure DevOps Cloud (inatech/Techoil)
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  [Scheduler]  9:30 AM IST daily (cron: 0 4 * * 1-5)   │
│       │                                                 │
│       ▼                                                 │
│  [Pipeline Agent — Ubuntu Free (Microsoft-hosted)]      │
│       │                                                 │
│       ├──► GET /release/definitions                     │
│       │    (all pipelines in Techoil-3.3.0 folder)     │
│       │                                                 │
│       ├──► GET /release/deployments  ← per pipeline     │
│       │    filter: BVT2 environment, latest only        │
│       │                                                 │
│       ├──► Build HTML email (Release Notes format)      │
│       │                                                 │
│       └──► Send → Microsoft Graph API → Team Group Email  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Files

| File | Purpose |
|---|---|
| `send_qc_email.py` | Main Python script — upload to ADO repo |
| `qc-email-pipeline.yml` | ADO pipeline YAML — upload to ADO repo |
| `email_preview.html` | Open in browser to preview exact email output |
| `email_template.html` | HTML template reference with placeholders |

---

## ADO REST API Endpoints Used

### 1. Get all release definitions in folder
```
GET https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/definitions
    ?path=\Inatech\Techoil New Pipelines\Techoil-3.3.0
    &api-version=7.0
```

### 2. Get latest BVT2 deployment per pipeline
```
GET https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/deployments
    ?definitionId={id}
    &queryOrder=descending
    &$top=20
    &api-version=7.0
```
Filter response where `releaseEnvironment.name == "BVT2"`.

---

## Email Format

Matches the Release Notes HTML table format:

```
Subject: QC Release Notes – BVT2 – 07 Apr 2026

┌──────────────────────────────────────────┐
│              Release Notes               │  ← black background, white text
├─────────────┬────────────────────────────┤
│ Date        │ 07 - Apr - 26              │
│ Time        │ 09 : 30 AM                 │
│ Version     │ 3.3.0 (Develop)            │
│ Environment │ BVT2 - https://qc1...      │
└─────────────┴────────────────────────────┘

┌──────┬──────────────────────────────────┬─────────────────┐
│ S.No │ Component              [#5B9BD5] │ Release version │
├──────┼──────────────────────────────────┼─────────────────┤
│  1   │ INA-Techoil-AKS-TechoilAPI-3.3.0 │ Release - 24   │
│  2   │ INA-Techoil-Client-3.3.0         │ Release - 29   │
│  3   │ INA-Techoil-Dacpac-3.3.0         │ Release - 23   │
│  4   │ INA-Techoil-MongoDB-3.3.0        │ Release - 3    │
│  5   │ One Time Script                  │ N/A            │  ← always N/A
└──────┴──────────────────────────────────┴─────────────────┘
```

---

## One-Time Setup Steps

### STEP 1 — Generate PAT Token
1. Go to `https://dev.azure.com/inatech`
2. Top-right → User Settings → Personal Access Tokens
3. Click **+ New Token**

   | Field | Value |
   |---|---|
   | Name | QCEmailAutomation |
   | Expiry | 1 year |
   | Scopes | Release → Read, Build → Read |

4. Copy and save the token (shown only once)

---

### STEP 2 — Create Repo in ADO
1. `dev.azure.com/inatech/Techoil` → Repos → New Repository
2. Name: `qc-email-automation`
3. Upload both files:
   ```
   qc-email-automation/
   ├── send_qc_email.py
   └── qc-email-pipeline.yml
   ```

---

### STEP 3 — Create the Pipeline
1. Pipelines → New Pipeline
2. Azure Repos Git → select `qc-email-automation`
3. Existing Azure Pipelines YAML file → select `qc-email-pipeline.yml`
4. Save (do not run yet)

---

### STEP 4 — Register an Azure AD App (one-time)
1. Go to `https://portal.azure.com` → **Azure Active Directory** → **App registrations** → **New registration**
2. Name: `QCEmailAutomation`, leave defaults, click **Register**
3. Note the **Application (client) ID** and **Directory (tenant) ID** from the Overview page
4. **Certificates & secrets** → **New client secret** → set expiry → copy the **Value** (shown once)
5. **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions** → search `Mail.Send` → Add
6. Click **Grant admin consent** for your organisation

---

### STEP 5 — Add Secret Variables
Pipeline → Edit → Variables → add these 6:

| Variable | Value | Secret (locked) |
|---|---|---|
| `ADO_PAT` | PAT token from Step 1 | Yes |
| `EMAIL_FROM` | sender@inatech.com | Yes |
| `EMAIL_TO` | team-group@inatech.com | No |
| `AZURE_CLIENT_ID` | App (client) ID from Step 4 | Yes |
| `AZURE_TENANT_ID` | Directory (tenant) ID from Step 4 | Yes |
| `AZURE_CLIENT_SECRET` | Client secret value from Step 4 | Yes |

> **Note:** `EMAIL_FROM` must be a mailbox in your tenant. The app sends mail *on behalf of* that user via the Graph API `users/{EMAIL_FROM}/sendMail` endpoint.

---

### STEP 6 — Test Run
1. Pipeline → Run pipeline (manual trigger)
2. Check logs: should show each pipeline found + BVT2 deployment
3. Verify email arrives with correct HTML format

---

## Pipeline Schedule (YAML)

```yaml
schedules:
  - cron: "0 4 * * 1-5"    # 04:00 UTC = 09:30 AM IST, Mon–Fri
    always: true             # runs even if no code changes
```

Timezone reference:

| Timezone | UTC offset | Cron for 9:30 AM |
|---|---|---|
| IST | UTC+5:30 | `0 4 * * 1-5` |
| GST | UTC+4:00 | `30 5 * * 1-5` |
| GMT | UTC+0:00 | `30 9 * * 1-5` |

---

## Maintenance

| Task | Action |
|---|---|
| PAT expires (1 year) | Generate new PAT → update `ADO_PAT` pipeline variable |
| Client secret expires | Azure AD → App registrations → QCEmailAutomation → new secret → update `AZURE_CLIENT_SECRET` |
| New pipeline added to folder | Automatic — script discovers all pipelines in folder |
| Pipeline removed from folder | Automatic — row disappears from email |
| Send on a non-scheduled day | Pipeline → Run pipeline (manual) |
| Skip a day | Disable the pipeline schedule temporarily |

---

## Cost

| Component | Cost |
|---|---|
| ADO Microsoft-hosted agent | Free (1,800 min/month included) |
| Script runtime per day | ~30 seconds |
| Microsoft Graph API | Free (included with M365 licence) |
| ADO REST API | Free |
| **Total** | **$0** |
