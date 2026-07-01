# Changelog

## v1.9.5

### Added

- `TemplateRegistry.get_default()`; template resolve chain: explicit → registry default → `"investigation"`
- `resolve_request_template()` as the single resolve entry point
- `run_synthesize_speech(..., timeout_sec=)`, `SynthesisTimeoutError`
- `on_synthesized(ctx, result)` callback; legacy `(result)` deprecated
- `make_run_context(deps)` helper for voiceover fallback outside `Agent.iter`
- `TemplateRegistryInfo.is_default` and `TemplateInfo.is_default`
- Env `SMART_TTS_SYNTHESIS_TIMEOUT_SEC` for optional default synthesis timeout

### Changed

- `SynthesizeSpeechRequest.template` default `None` (was `"investigation"`) — see migration
- `PreviewSpeechTextRequest.template` default `None` (was `"investigation"`)
- Default builtin registry resolves omitted template to `"default"` via `get_default()`

### Migration

- Pass `template="investigation"` explicitly if you relied on the implicit field default without a custom registry
- Update `on_synthesized` to accept `RunContext` as the first argument: `async def on_synthesized(ctx, result): ...`
- For programmatic synthesis outside the agent tool path, pass `ctx=make_run_context(deps)` when using the new callback signature
