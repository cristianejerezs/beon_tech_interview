# Production retention and deletion approval

**Status: NOT APPROVED. Production shared reuse must remain disabled.**

This is an approval checklist, not an approved policy or a claim of legal compliance.
The owner has not supplied retention durations or authorized backup deletion rules.
Default-on session grants are disclosed defaults, not affirmative consent clicks.
Production review must specifically approve whether that authorization model is suitable.

| Record | Current behavior | Owner decision still required |
|--------|------------------|-------------------------------|
| Identity mappings | Stable issuer/subject-derived hash in local records; OIDC claims are not copied to reports | Retention and deletion of identifiers, identity-provider records and logs |
| Private reports | Latest ten per analyst; owner can delete a private report | Time-based duration, inactive-account deletion, and backup expiry |
| Consent audit events | Append-only grant/withdrawal records, including notice version | Minimum retained audit period and deletion rules for linked artifacts |
| Shared FAQ/improvement copies | Separate copies survive withdrawal and private-report pruning/deletion | Duration, access policy, exceptional removal process and propagation |
| Backups | Deployment operator responsibility; no backup lifecycle is implemented | Schedule, encryption/access, expiry, deletion propagation and restore handling |
| Usage ledger | Local persisted reservations/settlements | Billing/audit retention and access policy without deleting unresolved reservations |

Before setting `AIRPORT_RETENTION_POLICY_APPROVED=true`, record:

1. Approver role and approval date; never use personal identifiers unnecessarily.
2. Approved durations and deletion procedures for every record class above.
3. Backup expiry/restore controls preventing deleted private data from reappearing.
4. Operator access, deletion request workflow, and evidence that the procedures were tested.
5. Review of provider-specific retention terms and default-on session authorization.

Do not treat this file's existence, a successful automated test, or a configuration flag
alone as owner approval. Reuse is blocked in production unless the configuration explicitly
asserts approval; operator review must keep that assertion truthful.
