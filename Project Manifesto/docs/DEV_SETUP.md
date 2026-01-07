# DEV_SETUP

## Prereqs
- Node.js LTS + npm (Windows or any OS).

## Install (frontend)
- `npm ci` (preferred) or `npm install`

## Dev server
- Default: `npm run dev` (Next.js default port 3000)
- Stable port (verified): `npm run dev:55210` (binds 0.0.0.0:55210)

## Validation
- `npm run typecheck`
- `npm run build`
- `npm run lint`

## Network issues (if npm fails)
- Example registry switch: `npm config set registry https://registry.npmjs.org/`
- Do not copy node_modules from other projects.
