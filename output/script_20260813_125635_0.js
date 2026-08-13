on
{
  "name": "saasweave",
  "private": true,
  "version": "0.1.0",
  "license": "MIT",
  "workspaces": [
    "apps/*",
    "packages/*"
  ],
  "scripts": {
    "dev": "turbo run dev --parallel",
    "dev:api": "turbo run dev --filter=api",
    "dev:web": "turbo run dev --filter=web",
    "build": "turbo run build",
    "lint": "turbo run lint",
    "db:push": "tsx apps/api/src/db/client.ts push"
  },
  "devDependencies": {
    "turbo": "^2.0.0",
    "tsx": "^4.7.0",
    "typescript": "^5.5.0"
  }
}
