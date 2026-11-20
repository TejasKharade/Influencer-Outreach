# Influencer Outreach Assistant

Working local implementation of the assignment workflow. Uses Instagram Graph API, Gemini API, Gmail, Google Sheets, SQLite, and Streamlit. It does not scrape Instagram or send AI replies without human approval.

## Setup

1. Install Python 3.11+ and run `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`; add the credentials described below. Do not commit `.env`, `token.json`, `client_secret.json`, or `outreach.sqlite3`.
3. In Google Cloud, enable Gmail and Sheets APIs; create a Desktop OAuth client and save its downloaded JSON as `client_secret.json`. Create a Sheet with a tab named `Leads` and set `GOOGLE_SHEET_ID`.
4. Run `python outreach.py auth` to complete Google sign-in. OAuth requests Gmail read, compose, and Sheets edit scopes.
5. Run `streamlit run app.py`. In another terminal, run `python outreach.py worker` and leave it running. The worker polls once per minute.
6. Create a campaign. Search Instagram manually using its niche, keywords, location, and follower range. For each relevant public profile, use **Add a publicly sourced lead** to record the username, name, niche/category, displayed follower count, publicly stated location (if any), public bio, and public business email or other contact detail (if any). The profile URL is generated from the username. The contact source URL helps document where a public business email appeared. Leave unavailable fields blank; do not guess them. Use an authorized test email for actual Gmail delivery. Then score, generate drafts, inspect them, sync the Sheet, and approve the initial batch. Set `DRY_RUN=0` only when ready to send to authorized test recipients. **Discover via Meta (optional)** needs Meta approval; the demo does not depend on it.

## Credentials and account configuration

| Setting | Source |
|---|---|
| `META_ACCESS_TOKEN`, `META_IG_USER_ID` | Meta developer app and authorized Instagram professional account with hashtag search and Business Discovery access |
| `META_GRAPH_VERSION` | Graph API version supported by that app |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini API key from Google AI Studio and supported model ID (default `gemini-3.5-flash-lite`); separate from the Instagram Graph token |
| `GOOGLE_CLIENT_SECRET_FILE`, `GOOGLE_TOKEN_FILE` | Google Desktop OAuth client JSON and locally generated refresh token |
| `GOOGLE_SHEET_ID` | Sample CRM Sheet URL |
| `SENDER_EMAIL` | Gmail account authorized through OAuth |
| Brand/offer/sender/opt-out/test recipients | Campaign form and authorized test setup |

Never paste secrets into the dashboard or source files. `DRY_RUN=1` is the default. The Sheet shows the current lead state; SQLite is the job ledger. The local machine and worker must remain on for real scheduled follow-ups.

If an access token appears in a screenshot, error report, or shared log, revoke it in Meta and replace `META_ACCESS_TOKEN` before running discovery again.

Meta hashtag discovery requires the **Instagram Public Content Access** feature. It is optional for the internship demo. The assignment permits a working demonstration with test data and authorized accounts. If you later want automated hashtag search, request that feature through Meta App Review. A valid token and professional account alone do not grant it.

The assignment rubric specifically names Claude AI. This project uses Gemini API at the user's request; explain that substitution in the submission if strict rubric compliance is required.

## Demonstration and submission

Use authorized test recipient addresses. Record a live run that shows discovery, public contact source, scoring, CRM sync, initial draft, human approval, Gmail delivery, a reply from the test recipient, AI classification/draft, human reply approval, and CRM update. To demonstrate the 4/6-day follow-up logic without waiting, edit `next_due_at` for a test lead to an earlier UTC timestamp in the local database, then run the worker; repeat for the second follow-up on an unanswered test thread. Show that a reply or opt-out clears `next_due_at`. Include the source folder, populated Sheet link, video, and sample initial/follow-up/reply messages.

## Operational notes

Meta Business Discovery applies to eligible professional accounts; official API access and fields must be verified with the chosen Meta app. A missing public email can be entered manually with an optional contact source URL. API failures appear in the UI or worker log. Gmail scope approval or verification may be needed beyond a private test deployment. The program never asks Gemini to execute email content as instructions.
