# Extension Notes (Phase 2+)

1. Implement `ApiWorkizService` with production credentials, pagination, and webhook sync reconciliation.
2. Add robust file storage adapter (S3/GCS) and signed URL upload strategy for photos.
3. Add AI polish endpoints per section using cautious prompts and explicit user approval before applying edits.
4. Add version history snapshots per assessment revision.
5. Add observation templates/snippets and exclusion libraries.
6. Improve PDF renderer to HTML-to-PDF pipeline for richer layouts and inline photo grids.
7. Add background sync jobs and sync health dashboards from `WorkizSyncLog`.
