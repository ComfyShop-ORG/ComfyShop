# Repository conventions

- UI acceptance: dark neutral surfaces, square corners, restrained borders, functional Chinese copy, 工作机 terminology. Keep the login Logo. Do not add slogans or implementation-stage labels to the interface.
- `packages/tokens/src/tokens.json` is the only color source. Generate CSS; do not edit generated output. Shared sizing and spacing belong in tokens.
- Consume Radix through `@comfyshop/ui`. Preserve native input/button semantics, spread props, forward refs, and use Radix composition for behavior. Do not introduce feature-local control variants to bypass the design system.
- All media collections use `@comfyshop/media`. Use stable item IDs, append cursor pages immutably, and change `resetKey` when item indices change. Supply original media dimensions and the actual dialog scroll element.
- Business data comes from FastAPI. Do not introduce localStorage identities, synthetic execution, fixture catalogs or silent local fallbacks. A submitted task remains queued until a real work machine executes it.
- Backend routes live in `api/`, shared workflow rules in `services/`. Persist schema changes through Alembic. Regenerate `packages/api-client` contracts with `pnpm api:generate` when API schemas change.
- Keep route handlers thin and reuse the single definitions listed in `docs/architecture.md` (status constants, soft-delete filter, write lock, cursor paging, ownership lookup, typed API client) instead of re-implementing them. Annotate API function parameters.
- API entrypoints use APIRouter and dependency injection. GPU execution belongs to work machines. Do not use FastAPI BackgroundTasks for GPU jobs or put ComfyUI/Torch dependencies in the API environment.
- Do not add empty packages, speculative abstractions, duplicated components or CSS override stacks. Keep packages independently meaningful.
- Update docs when implemented scope changes. Run `pnpm check`, `pnpm test`, `pnpm build`; verify affected UI at desktop and mobile widths. Only add tests for meaningful contracts or behavior.
- Versioned docs describe product behavior, configuration, constraints, and reproducible validation. Exclude conversational delivery notes, one-off deployment status, private host addresses, account or task identifiers, and machine-specific backup paths. Label configurable defaults and generic examples explicitly.
- Keep backups, source archives, secrets, runtime state, and hosting metadata such as `.openai/` outside the public repository.
