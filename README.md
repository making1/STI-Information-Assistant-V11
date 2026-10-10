# STI Information Assistant — GitHub/Streamlit Ready
Bilingual English/Kiswahili educational/research prototype. It is not a diagnostic or prescribing system.

## Deploy
Upload this folder's contents to the root of a GitHub repository. In Streamlit Community Cloud create an app from the repository, choose `main`, and set the entrypoint to `app.py`.

In Streamlit App Settings > Secrets add:
```toml
ADMIN_USERNAME = "your-admin-name"
ADMIN_PASSWORD = "your-long-unique-password"
```
Do not commit real credentials. `.gitignore` excludes `.streamlit/secrets.toml` and `sti_app.db`.

## Local run
Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` as environment variables, then:
```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Content governance
All seeded content is `pending_review`; only explicitly approved content is learner-visible. The application does not manufacture expert approval. A qualified Kenyan STI clinician/public-health reviewer and Kiswahili health-communication reviewer should approve content before real deployment.

## Important persistence note
This prototype uses SQLite. Hosted Streamlit local storage is not durable production storage; approvals, audit records, and inquiries may be lost on rebuild/replacement. For a real pilot/production system requiring persistent records, migrate the SQLAlchemy connection to a managed persistent database and complete security/privacy review.

The bundled TF-IDF + Logistic Regression model and tiny bilingual training dataset demonstrate the NLP pipeline; their evaluation is not research-grade validation.


## Changing the deployed admin login
`ADMIN_USERNAME` and `ADMIN_PASSWORD` in Streamlit App Settings > Secrets are authoritative. After changing either value, save the Secrets and reboot/redeploy the app. On startup, the application synchronizes the admin account automatically; no manual database editing is required.

## V3 aggregate demographic reporting
The learner interface can collect, with separate explicit consent, gender, age bracket (18–19, 20–22, 23–25), sexual activity status, residence at county/town level, and nearest health facility. The Admin → Aggregate reporting tab displays grouped counts only. Users can choose “Prefer not to say” for sensitive fields. Residence guidance explicitly discourages home addresses. Demographic records are covered by the retention cleanup.

This reporting feature is for research/educational analytics, not diagnosis or clinical decision-making.


## V4 model evaluation
The intent model was retrained on a larger balanced synthetic dataset and evaluated on held-out phrasing templates. See `evaluation/metrics.json`, `classification_report.csv`, `confusion_matrix.csv`, and `CHAPTER_4_TEST_RESULTS.md`. These are prototype/synthetic results, not clinical validation.


## V5 passive behavioral analytics
Routine use now records pseudonymous sessions, user messages, turns, session duration, requested topics, response completion/drop-off proxies, return visits, and clicks on testing/prevention/referral service resources. Admin → Usage analytics reports aggregate values. See `docs/BEHAVIORAL_ANALYTICS.md` for definitions and limitations.


## V6
Raw NLP extraction is no longer shown to learners. Intent, STI topic, symptom, exposure and duration extraction is aggregated in Admin → Usage analytics.


## V7 continuous conversations
Learners can ask multiple questions in one session, see conversation history, and explicitly end/start a new session. Closing the browser cannot reliably trigger a server-side end event.
\n\n## V8 resource routing\nIntent classes now determine which STI resource categories are shown. Symptoms additionally trigger testing guidance. The learner receives reviewer-approved content when available; otherwise the application explicitly states that reviewed content is unavailable. Resources are informational links, not verified appointments or facility-level referrals.\n\n\n## V9 classification\nRule-assisted LinearSVC intent routing. See evaluation folder for updated synthetic test results.\n\n\n## V10 response selection\nResponses now prioritize approved content by disease+intent, then intent, then disease, then general fallback. Added 24 English/Kiswahili intent-specific draft entries, all pending_review. A qualified reviewer must approve them before learners see them. Existing databases require admin creation/approval of new content because seeding runs only on an empty content table.\n

## V11 specific concerns
Distinct concern matching for itching, painful urination, yellow urine, genital discharge and sores. Each has bilingual draft content, imported as pending_review even into an existing database; a qualified reviewer must approve before learner display. Unapproved concern content is never displayed as medical guidance. Conversation Markdown newlines fixed.
