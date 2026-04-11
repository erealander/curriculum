# Rolling Suds Property Cleaning Plan Builder (MVP Phase 1)

Full-stack TypeScript app optimized for Rolling Suds estimate enhancement workflow.

## Stack
- Frontend: React + TypeScript (Vite)
- Backend: Node.js + Express + TypeScript
- DB: PostgreSQL + Prisma
- PDF generation: PDFKit
- Auth: internal JWT login

## Implemented MVP capabilities
- Login flow for internal estimators.
- **Import from Workiz** screen with modular adapter architecture.
- Workiz mock service with appointment search/import.
- Core entities for customers, properties, appointments, estimates, line items, assessments, observations, tags, pricing options, photos, sync logs.
- Dictation-friendly assessment editor with large textareas and autosave patterns.
- Hybrid tags + notes workflow (system tags + custom tags).
- Live client preview panel beside editor.
- PDF export endpoint for branded client-ready plan.
- Branding/settings model scaffold.
- Seeded realistic Rolling Suds demo record (algae, tiger striping, patio soiling, good/better/best pricing).

## Quick start
```bash
npm install
cp .env.example .env
npm run db:generate
npm run db:migrate
npm run db:seed
npm run dev
```

Demo login:
- `estimator@rollingsuds.com`
- `rolling123!`

## Architecture notes
- `apps/server/src/services/workiz.ts` defines the Workiz service abstraction.
- `MockWorkizService` is default via `WORKIZ_MODE=mock`.
- `ApiWorkizService` is intentionally stubbed with TODOs for production endpoint mapping.
- Import flow stores external IDs and raw payload snapshots for debugging/sync traceability.

## Phase 2 extension notes
See `docs/extension-notes.md`.
