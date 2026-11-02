# External platform reply integrations

The outbox relay dispatches `review.reply.publish.requested` events to
`process_outbox_integration_job`. The event payload must contain:

```json
{
  "tenant_id": "company UUID",
  "platform": "yandex",
  "review_external_id": "platform review ID",
  "text": "approved reply text"
}
```

Credentials are not included in the outbox payload. The job establishes the
tenant RLS context, reads `encrypted_credentials` from `tenant_integrations`,
and decrypts its JSON object with the configured `ENCRYPTION_KEY`. The Yandex
adapter currently expects an `access_token` property and sends the reply as
`{"text": "..."}` to the Yandex Business reviews reply endpoint. Confirm the
endpoint path and response field (`external_reply_id`) against the Yandex API
contract enabled for the account before production use.

HTTP 429 and 5xx responses and network errors are retried by ARQ. Other 4xx
responses are logged as permanent failures and are not retried. Credentials
and reply text are not written to logs.
