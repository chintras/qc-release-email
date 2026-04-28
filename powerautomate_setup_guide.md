# Power Automate Setup — Techoil BVT QC Release Email

## Your Configuration
- ADO Org     : inatech
- ADO Project : Techoil
- Environment : BVT
- Schedule    : 9:30 AM daily
- Recipient   : Team group email

---

## STEP 1 — Create Azure DevOps PAT Token

1. Go to: https://dev.azure.com/inatech
2. Top-right → User Settings (person icon) → Personal Access Tokens
3. Click "+ New Token"
4. Fill:
   - Name       : QCEmailAutomation
   - Expiration : 1 year
   - Scopes     : Custom defined
     ✅ Release → Read
     ✅ Build   → Read
5. Click Create → COPY the token (shown only once)
6. Encode it for Basic Auth:
   - Open: https://www.base64encode.org/
   - Encode: :{your-PAT-token}    (colon before token, no username)
   - Save the encoded string

---

## STEP 2 — Find Your Release Pipeline ID

Call this in browser (replace PAT with yours):

  URL: https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/definitions?api-version=7.0

Or use Postman:
  GET https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/definitions?api-version=7.0
  Auth: Basic  (username: blank, password: your-PAT)

From the response, find your BVT pipeline → note its "id" number

---

## STEP 3 — Key API Endpoints (Your Org Pre-filled)

### Get latest deployment for BVT environment:
  GET https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/deployments
      ?definitionId={YOUR_PIPELINE_ID}
      &definitionEnvironmentId={YOUR_BVT_ENV_ID}
      &queryOrder=descending
      &$top=1
      &api-version=7.0

### Get release details (artifacts/components):
  GET https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/releases/{releaseId}
      ?api-version=7.0

### Response fields you need:
  - release.name              → Release name / version
  - completedOn               → Date & Time of deployment
  - releaseEnvironment.name   → BVT
  - release.artifacts[]       → Component list
    - alias                   → Component name
    - definitionReference.version.name → Release version number

---

## STEP 4 — Power Automate Flow (Step by Step)

### Go to: https://make.powerautomate.com
### Sign in with your Office 365 account

---

### FLOW NAME: Techoil BVT QC Release Email

---

### [Action 1] TRIGGER — Recurrence (Scheduler)
  Type        : Recurrence
  Interval    : 1
  Frequency   : Day
  Time zone   : (your timezone — e.g. India Standard Time)
  Start time  : Set to any date at 09:30:00
  At these hours   : 9
  At these minutes : 30

---

### [Action 2] Initialize Variable — HTML Rows
  Name  : varHTMLRows
  Type  : String
  Value : (empty)

---

### [Action 3] HTTP — Get Latest BVT Deployment
  Method : GET
  URI    : https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/deployments?definitionId={PIPELINE_ID}&queryOrder=descending&$top=1&api-version=7.0
  Headers:
    Authorization : Basic {your-base64-encoded-PAT}
    Content-Type  : application/json

---

### [Action 4] Parse JSON — Deployment Response
  Content : Body (from Action 3)
  Schema  : (click "Generate from sample" → paste API response)

  Key fields to extract:
    - value[0].release.id
    - value[0].release.name
    - value[0].completedOn
    - value[0].releaseEnvironment.name

---

### [Action 5] HTTP — Get Release Details (Artifacts)
  Method : GET
  URI    : https://vsrm.dev.azure.com/inatech/Techoil/_apis/release/releases/@{body('Parse_JSON')?['value'][0]?['release']?['id']}?api-version=7.0
  Headers:
    Authorization : Basic {your-base64-encoded-PAT}
    Content-Type  : application/json

---

### [Action 6] Parse JSON — Release Details
  Content : Body (from Action 5)
  Key fields:
    - artifacts[].alias
    - artifacts[].definitionReference.version.name

---

### [Action 7] Apply to Each — Loop Artifacts
  Input : artifacts array from Action 6

  Inside loop:
    [7a] Append to string variable — varHTMLRows
    Value:
      <tr>
        <td style="text-align:center;">@{add(iterationIndexes('Apply_to_each'), 1)}</td>
        <td>@{items('Apply_to_each')?['alias']}</td>
        <td>Release - @{items('Apply_to_each')?['definitionReference']?['version']?['name']}</td>
      </tr>

---

### [Action 8] Compose — Format Date & Time
  Use expressions:
    Date : formatDateTime(utcNow(), 'dd - MMM - yy')
    Time : formatDateTime(utcNow(), 'hh : mm tt')

---

### [Action 9] Compose — Build Full HTML Body
  Value: (paste the full HTML — replace placeholders)

  Replace:
    {{DATE}}            → @{outputs('Format_Date')}
    {{TIME}}            → @{outputs('Format_Time')}
    {{VERSION}}         → @{body('Parse_JSON_Deployment')?['value'][0]?['release']?['name']}
    {{ENV_NAME}}        → BVT
    {{ENV_URL}}         → https://bvt.techoil.com/   (confirm your actual URL)
    {{COMPONENT_ROWS}}  → @{variables('varHTMLRows')}

---

### [Action 10] Send an Email (V2) — Outlook Connector
  To      : your-team-group@inatech.com
  Subject : QC Release Notes - BVT - @{formatDateTime(utcNow(), 'dd MMM yyyy')}
  Body    : @{outputs('Compose_HTML')}
  ✅ Check: "Is HTML" = Yes

---

## STEP 5 — Test Before Scheduling

1. In Power Automate, click "Test" → Manual
2. Run the flow
3. Check your email for the formatted output
4. If artifacts are missing, verify pipeline ID and environment ID

---

## NOTES
- PAT token expires in 1 year → set a calendar reminder to renew it
- Flow runs in Microsoft cloud — your machine being OFF has no impact
- If BVT deployment didn't happen that day, add a Condition to skip email
