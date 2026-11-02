# External reply publishing

The outbox relay dispatches `publish_review_reply` events to the
canonical `publish_review_reply` ARQ task. Payloads contain only the tenant and
internal review identifiers:

```json
{
  "tenant_id": "company UUID",
  "review_id": "review UUID"
}
```

The task loads the approved reply and platform credentials from the tenant's
`review_replies`, `reviews`, and `platform_integrations` rows under RLS. API and
refresh tokens are decrypted with `ENCRYPTION_KEY`. Database work is split
around the platform request: credentials are loaded and the session is closed,
the HTTP request runs without a DB transaction, then the external reply ID or
publication error is stored in a new short tenant-scoped transaction.

Publication status is exposed on each approved draft as `queued_outbox`,
`publishing`, `published`, or `publish_failed`. Approving a draft creates its
reply and outbox event in one transaction. Permanent failures can be retried
through `POST /api/v1/reviews/{review_id}/drafts/{draft_id}/retry-publication`;
that endpoint resets the reply to `queued_outbox` and inserts a fresh outbox
event atomically.

The Yandex adapter currently expects `external_id` on the review and sends
`{"text": "..."}` to the Yandex Business reviews reply endpoint using the
OAuth token. Verify the endpoint path and response field
(`external_reply_id`) against the API contract enabled for the account before
production use. HTTP 429 and 5xx and network errors are retried by ARQ. Other
4xx responses are recorded as permanent failures. Credentials and reply text
are not written to logs.
