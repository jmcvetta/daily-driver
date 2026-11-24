# Testing standards

Read this document when writing, changing, or reviewing tests.

## Application tests

- Code without tests is broken. Add proportionate regression coverage with the
  code it protects.
- Tests assert observable behavior and fail loudly on defects.
- Tests run offline against fixtures, not live third parties. Manual checks are
  not tests.
- Cover silent errors and plausible consumer-visible regressions.
- A test communicates the wrong behavior it catches through its name,
  arrangement, assertions, or a comment where the structure alone is unclear.
  No prescribed statement is required, and a behaviorally clear test without
  dedicated prose remains valid.
- Delete tests that provide no useful consumer-visible protection, are
  tautological, or otherwise fail this standard. Missing explanatory prose
  alone is never grounds for deletion.
- OpenTofu-like declarations use offline `validate`. Test production
  infrastructure with infrastructure tools, not ad hoc scripts.

## Testing machinery

Do not test tests or testing machinery unless that machinery is the shipped
product. This includes tests of checks, lint and static analysis, CI,
selectors and filters, fixtures, fakes, helpers, evaluation harnesses,
graders, judges, and rendered evaluation results.
