# Google Integrations — Calendar / Meet, Drive and Analytics

This release intentionally enables only:

- Google Calendar / Meet
- Google Drive uploads
- Google Analytics GA4 reports and local charts
- Integration Sync Logs

Google Sheets, Google Ads, Google Leads and the Ads webhook remain deferred. Their old database structures are preserved for a later release, but their URLs, dashboard cards, sidebar entries and OAuth scopes are disabled.

## Files to replace

Replace the complete folder:

`backend/apps/integrations`

Also replace:

`backend/apps/core/context_processors.py`

The second file moves **Integrations** to the final sidebar position, below **System**, and only shows the enabled tools.

## Database

No new migration is required.

The Analytics chart series is stored inside the existing `GoogleAnalyticsSnapshot.raw_response` JSON field.

## Current OAuth scopes

The CRM requests least-privilege access only for the enabled tools:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/calendar.events`
- `https://www.googleapis.com/auth/drive.file`
- `https://www.googleapis.com/auth/analytics.readonly`

Google Sheets and Google Ads scopes are not requested.

## Required company configuration

Open:

`Integrations > Configure Google App`

Configure:

- Google OAuth Client ID
- Google OAuth Client Secret
- Google Calendar ID (`primary` is normally correct)
- Optional Google Drive Folder ID
- Numeric GA4 Property ID

The Client Secret and Google token payloads are encrypted before database storage and are not rendered back in plain text.

## Production encryption key

For production, configure a dedicated Fernet key outside Git:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the generated value in the server environment:

```env
INTEGRATION_ENCRYPTION_KEY=PASTE_THE_GENERATED_KEY_HERE
```

Do not change this key after encrypted data has been stored unless you first perform a controlled key rotation.

A Django security check now warns when production is using the `SECRET_KEY` fallback instead of a dedicated integration key.

## Important after replacing

The previous Google authorization may contain Sheets or Ads permissions. To apply the reduced scope set:

1. Open Integrations.
2. Disconnect Google.
3. Connect Google again.
4. Approve only Calendar, Drive and Analytics permissions.

## Analytics charts

Each Analytics synchronization now makes:

1. One GA4 request for accurate period totals.
2. One GA4 request with the `date` dimension for the daily chart series.

The Analytics page displays:

- Active users
- Sessions
- Conversions
- Revenue
- Users and sessions chart
- Conversions and revenue chart
- Previous snapshots

No external chart library or CDN is required. Charts are rendered locally using HTML Canvas and safely embedded JSON.

## Local validation

From `backend`:

```bash
python manage.py check
python manage.py check --deploy
python manage.py runserver
```

Then test:

1. Configure Google App.
2. Disconnect/reconnect Google.
3. Create a Calendar / Meet event.
4. Upload a file to Drive.
5. Synchronize a GA4 date range.
6. Confirm that the charts appear.
7. Review Integrations > Sync Logs.

## Security decisions in this release

- Company-bound configuration and records remain enforced.
- Role/module permission checks remain enforced.
- Sensitive values remain encrypted and masked.
- OAuth uses a state value and offline refresh tokens.
- Deferred APIs are not exposed through active routes.
- OAuth scope collection is reduced to the enabled tools.
- Analytics chart JSON uses Django `json_script` instead of unsafe inline interpolation.
