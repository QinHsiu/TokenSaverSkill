# B1 acceptance matrix (T1–T16 → pytest)

| ID | Test(s) | Notes |
|----|---------|-------|
| T1 | `test_ensure_runtime_creates_config` | Cold start runtime + config |
| T2 | `test_ensure_creates_and_reuses` | UUID file create/reuse |
| T3 | `test_upward_finds_parent_file`, `test_stop_after_8_levels_creates_at_original`, `test_git_does_not_stop`, `test_system_dir_stops_upward_search` | Upward search hard-stops |
| T4 | `test_env_override_no_writeback` | Env wins; no write-back |
| T5 | `test_archive_success`, `test_handle_format` | Handle format + event line |
| T6 | `test_archive_below_threshold` | Below threshold → exit 1 |
| T7 | `test_archive_missing_file` | Missing file → exit 4 |
| T8 | `test_recall_respects_max_tokens`, `test_recall_unknown_handle` | max-tokens; unknown handle → exit 5 |
| T9 | `test_concurrent_appends_no_partial_lines` | Concurrent record safety |
| T10 | `test_record_bad_mechanism` | Bad mechanism → exit 2 |
| T11 | `test_payload_string_and_file_equivalent` | `--payload-file` ≡ `--payload` |
| T12 | `test_audit_estimates` | Text estimates |
| T13 | `test_audit_json_format` | JSON audit stable |
| T14 | — | Manual: `install.sh` copies only (task-8 smoke) |
| T15 | `test_archive_disabled` | `enabled: false` → exit 1 |
| T16 | `test_list_empty_and_ordered` | Empty + ordered list |
