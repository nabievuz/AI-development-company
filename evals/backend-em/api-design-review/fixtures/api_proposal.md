# RFC — public Orders API v2 changes

**Author:** backend-eng-2
**Reviewer:** Backend EM

## Proposed changes

1. `GET /orders` — existing public endpoint. Currently returns every order
   for the account in one response with no `limit`/`cursor` params. This RFC
   ships it unchanged; order volume is expected to grow 10x next quarter.
2. The existing public field `user_id` in the `GET /orders/{id}` response is
   renamed to `userId` to match a new internal naming convention. No
   deprecation window, no old-field alias, no changelog entry planned for
   external API consumers.
3. New endpoint `POST /orders/{id}/refund` is added directly under the
   unversioned path `/orders/{id}/refund` (all other public endpoints in
   this API live under `/v1/...`).
4. New endpoint accepts a JSON body and requires the existing `Authorization`
   bearer header, consistent with the rest of the API.

## Candidate issues (for the reviewer to select from)

- `breaking_change` — a public response shape/field changes in a way that
  breaks existing clients without a deprecation path.
- `missing_pagination` — a public list endpoint returns an unbounded result
  set.
- `missing_versioning` — a new public endpoint is not placed under the
  existing API version prefix used by its siblings.
- `uses_json_body` — the endpoint accepts a JSON request body.
- `has_auth_header` — the endpoint requires the standard bearer auth header.
