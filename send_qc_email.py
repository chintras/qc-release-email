import requests
import base64
import os
import re
from datetime import datetime
from pathlib import Path

# Load .env from the same directory as this script
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed; fall back to existing env vars

# ── Configuration ──────────────────────────────────────────────────────────────
ADO_ORG         = "inatech"
ADO_PROJECT     = "Techoil"
PIPELINE_FOLDER = r"\Inatech\Techoil New Pipelines\Techoil-3.3.1"
ENV_NAME        = "QC1"
QC_URL          = "https://qc1.techoil.com/"
VERSION_LABEL   = "3.3.1 (Develop)"

TEMPLATE_PATH   = Path(__file__).parent / "email_template.html"

# ── Credentials (loaded from .env or environment) ──────────────────────────────
ADO_PAT             = os.environ["ADO_PAT"]
EMAIL_FROM          = os.environ.get("EMAIL_FROM", "internal-mail@inatech.onmicrosoft.com")
EMAIL_TO            = os.environ["EMAIL_TO"]
AZURE_CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID", "04fd78b5-7cf3-4020-a20e-d91ac34d42ac")
AZURE_TENANT_ID     = os.environ.get("AZURE_TENANT_ID", "01907b14-94ae-4806-a223-edcb38703c9d")
AZURE_CLIENT_SECRET = os.environ["AZURE_CLIENT_SECRET"]

# ── Azure DevOps Auth ───────────────────────────────────────────────────────────
_encoded_pat = base64.b64encode(f":{ADO_PAT}".encode()).decode()
ADO_HEADERS  = {
    "Authorization": f"Basic {_encoded_pat}",
    "Content-Type":  "application/json",
}
VSRM_BASE = f"https://vsrm.dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis"


def get_release_definitions():
    url    = f"{VSRM_BASE}/release/definitions"
    params = {"path": PIPELINE_FOLDER, "api-version": "7.0"}
    r = requests.get(url, headers=ADO_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    defs = r.json().get("value", [])
    print(f"[INFO] Found {len(defs)} pipelines in folder")
    return defs


def get_latest_bvt_deployment(definition_id, definition_name):
    url    = f"{VSRM_BASE}/release/deployments"
    params = {
        "definitionId": definition_id,
        "queryOrder":   "descending",
        "$top":         20,
        "api-version":  "7.0",
    }
    r = requests.get(url, headers=ADO_HEADERS, params=params, timeout=30)
    r.raise_for_status()

    for dep in r.json().get("value", []):
        env_name = dep.get("releaseEnvironment", {}).get("name", "")
        if env_name.strip().upper().startswith(ENV_NAME.upper()):
            print(f"  [OK]  {definition_name} ->{dep['release']['name']}")
            return dep

    print(f"  [--]  {definition_name} ->no {ENV_NAME} deployment found")
    return None


def format_release_version(release_name):
    if not release_name:
        return "N/A"
    match = re.match(r"(?i)(release)[^0-9]*(\d+)", release_name)
    if match:
        return f"Release - {match.group(2)}"
    return release_name


def build_html(results):
    """Fill email_template.html placeholders with live DevOps data."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    now      = datetime.now()
    date_str = now.strftime("%d - %b - %y")   # 28 - Apr - 26
    time_str = now.strftime("%I : %M %p")      # 09 : 30 AM

    # Build component rows
    rows_html = ""
    for idx, (defn, dep) in enumerate(results, start=1):
        component   = defn["name"]
        rel_version = format_release_version(dep["release"]["name"]) if dep else "N/A"
        rows_html += (
            f"\n    <tr>"
            f"\n      <td style=\"text-align:center; padding:6px 10px;\">{idx}</td>"
            f"\n      <td style=\"padding:6px 10px;\">{component}</td>"
            f"\n      <td style=\"padding:6px 10px;\">{rel_version}</td>"
            f"\n    </tr>"
        )

    # Append static "One Time Script" row
    rows_html += (
        f"\n    <tr>"
        f"\n      <td style=\"text-align:center; padding:6px 10px;\">{len(results) + 1}</td>"
        f"\n      <td style=\"padding:6px 10px;\">One Time Script</td>"
        f"\n      <td style=\"padding:6px 10px;\">N/A</td>"
        f"\n    </tr>"
    )

    env_cell = f"<strong>{ENV_NAME}</strong> &ndash; <a href=\"{QC_URL}\" style=\"color:#0563C1;\">{QC_URL}</a>"

    replacements = {
        "{{DATE}}":            date_str,
        "{{TIME}}":            time_str,
        "{{VERSION}}":         VERSION_LABEL,
        "{{ENV_NAME}}":        ENV_NAME,
        "{{ENV_URL}}":         QC_URL,
        "{{COMPONENT_ROWS}}":  rows_html,
    }

    # Replace ENV_NAME + ENV_URL as a combined cell (matches the template's combined pattern)
    template = template.replace(
        "<strong>{{ENV_NAME}}</strong> -\n        <a href=\"{{ENV_URL}}\" style=\"color: #0563C1;\">{{ENV_URL}}</a>",
        env_cell,
    )
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def get_access_token():
    url  = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     AZURE_CLIENT_ID,
        "client_secret": AZURE_CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
    }
    r = requests.post(url, data=data, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def send_email(html_body, subject):
    token = get_access_token()

    recipients = [
        {"emailAddress": {"address": addr.strip()}}
        for addr in EMAIL_TO.split(",")
        if addr.strip()
    ]

    payload = {
        "message": {
            "subject":      subject,
            "body":         {"contentType": "HTML", "content": html_body},
            "from":         {"emailAddress": {"address": EMAIL_FROM}},
            "toRecipients": recipients,
        },
        "saveToSentItems": "false",
    }

    url     = f"https://graph.microsoft.com/v1.0/users/{EMAIL_FROM}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    print(f"[INFO] Email sent ->{EMAIL_TO}")


def main():
    print(f"[START] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    definitions = get_release_definitions()
    if not definitions:
        print("[WARN] No pipelines found — email skipped.")
        return

    results = []
    for defn in definitions:
        dep = get_latest_bvt_deployment(defn["id"], defn["name"])
        results.append((defn, dep))

    html    = build_html(results)
    today   = datetime.now().strftime("%d %b %Y")
    subject = f"QC Release for Techoil – {ENV_NAME} – {today}"

    send_email(html, subject)
    print("[DONE] Finished.")


if __name__ == "__main__":
    main()
