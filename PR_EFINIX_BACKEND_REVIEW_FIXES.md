# PR Title

build: efinix: fix backend defaults, project generation, and toolchain detection

# PR Message

## Summary

This fixes the issues found during review of the Efinix build backend integration.

- apply Efinity default map/pnr/pgm parameters consistently in both CLI and direct Python build flows
- forward `infer-sync-set-reset` into generated Efinity project settings
- preserve non-header source library assignments in generated Efinity project XML
- fix SEU auto-mode generation so `WAIT_INTERVAL` is emitted when requested
- detect the Efinity installation from either `LITEX_ENV_EFINITY` or tools exposed on `PATH`
- share Efinity environment loading across the backend, platform, and programmer code paths
- add focused unit coverage for the Efinix backend plumbing and generator behavior

## Testing

- `pytest -q test/test_efinix.py`

## Notes

The change is split into three commits to keep review straightforward:

- `b0622815b` `build: efinix: apply default Efinity params consistently`
- `8982a6a01` `build: efinix: preserve libraries in generated project data`
- `761f62ca0` `build: efinix: detect the toolchain from PATH`
