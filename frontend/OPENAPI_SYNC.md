# OpenAPI-to-TypeScript Sync Setup

This document explains how to use the automated OpenAPI-to-TypeScript generation pipeline for end-to-end type safety between FastAPI (backend) and React (frontend).

## Overview

The frontend now uses `openapi-typescript` and `openapi-fetch` to automatically generate TypeScript types from the FastAPI OpenAPI schema. This eliminates the risk of runtime errors when the backend schema changes.

## Installation

Dependencies are already installed in `package.json`:
```json
{
  "openapi-typescript": "^7.4.5",
  "openapi-fetch": "^0.1.0"
}
```

## Setup Instructions

### 1. Start the FastAPI Backend

Ensure your FastAPI backend is running locally:
```bash
# From the backend directory
uvicorn app.main:app --reload --port 8000
```

### 2. Generate TypeScript Types

Run the type generation script:
```bash
npm run typegen
```

This command:
- Fetches `http://localhost:8000/openapi.json` from the running backend
- Generates strict TypeScript types into `src/api/schema.d.ts`
- Creates type definitions for all API endpoints, parameters, and responses

### 3. (Optional) Change Base URL

If your backend runs on a different URL, set the environment variable:
```bash
# .env.local
VITE_API_BASE_URL=http://your-backend-url:8000
```

## Usage

### Using the Type-Safe API Client

Import the client from `@/api/openapi-client`:

```typescript
import { api, createOpenAPIClient } from '@/api/openapi-client';

// Unauthenticated requests
const { data, error } = await api.getReviews({
  query: { page: 1, page_size: 50 }
});

// Authenticated requests
const token = localStorage.getItem('token');
const client = createOpenAPIClient(token);
const { data, error } = await client.GET('/api/v1/reviews', {
  params: { query: { page: 1 } }
});
```

### Using Type-Safe Hooks

Use the new hooks in `@/hooks/api/useReviewsOpenAPI`:

```typescript
import { useReviewsOpenAPI, useUpdateReviewStatusOpenAPI } from '@/hooks/api/useReviewsOpenAPI';

// Fetch reviews with full type safety
const { data, isLoading, error } = useReviewsOpenAPI({
  page: 1,
  page_size: 50,
  sentiment: 'NEGATIVE'
});

// Update review status with type-safe mutation
const updateStatus = useUpdateReviewStatusOpenAPI();

const handleUpdate = async () => {
  await updateStatus.mutateAsync({
    reviewId: 'uuid',
    newStatus: 'resolved',
    siResponse: 'Thank you for your feedback'
  });
};
```

## How It Eliminates Silent API Drift

### Before (Manual Types)
```typescript
// Manual type definition - can get out of sync
interface Review {
  id: string;
  platform: string;
  rating: number;
  text: string;
  // If backend adds a new field, this breaks silently
}

const { data } = await axios.get('/api/v1/reviews');
const review = data as Review; // Unsafe cast
```

### After (Auto-Generated Types)
```typescript
// Types are generated from the actual OpenAPI schema
import type { paths } from '@/api/schema';

// TypeScript knows the exact structure
const { data, error } = await api.getReviews({
  query: { page: 1, page_size: 50 }
});

// If backend changes the schema:
// 1. npm run typegen will generate new types
// 2. TypeScript will show compile-time errors
// 3. No runtime surprises
```

## Benefits

1. **Compile-Time Error Detection**: If the backend schema changes, TypeScript catches it before runtime
2. **IDE Autocomplete**: Full autocomplete for all API endpoints, parameters, and responses
3. **No Manual Type Definitions**: Types are automatically generated from the source of truth (OpenAPI)
4. **Refactoring Safety**: Rename endpoints or parameters, and TypeScript shows all affected code
5. **Type Inference**: TanStack Query automatically infers request/response types from the schema

## CI/CD Integration

Add to your CI pipeline to ensure types are always in sync:

```yaml
# .github/workflows/frontend.yml
- name: Generate OpenAPI Types
  run: |
    npm run typegen
    git diff --exit-code src/api/schema.d.ts
```

This will fail the build if the generated types have changed (indicating a backend schema change that needs frontend updates).

## Migration Strategy

1. **Phase 1**: Run `npm run typegen` to generate types
2. **Phase 2**: Create new hooks using the type-safe client (see `useReviewsOpenAPI.ts`)
3. **Phase 3**: Gradually migrate existing hooks one by one
4. **Phase 4**: Remove old Axios-based hooks once all are migrated

## Troubleshooting

### "ECONNREFUSED" Error
Ensure the FastAPI backend is running on port 8000 before running `npm run typegen`.

### Type Errors After Regeneration
If you see TypeScript errors after regenerating types:
1. The backend schema may have changed
2. Update your code to match the new schema
3. Run `npm run typecheck` to verify

### Missing Endpoints
If an endpoint is missing from the generated types:
1. Check if the endpoint is defined in FastAPI
2. Ensure the endpoint is not excluded from OpenAPI
3. Regenerate types with `npm run typegen`

## Resources

- [openapi-typescript Documentation](https://openapi-ts.pages.dev/)
- [openapi-fetch Documentation](https://openapi-ts.pages.dev/openapi-fetch/)
- [FastAPI OpenAPI Generation](https://fastapi.tiangolo.com/tutorial/first-steps/)
