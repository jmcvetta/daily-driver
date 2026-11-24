# Testing standards

Read this document when writing, changing, or reviewing tests.

## Application tests

- Code without tests is broken. Add proportionate regression coverage with the
  code it protects.
- Tests assert observable behavior and fail loudly on defects.
- Tests run offline against fixtures, not live third parties. Manual checks are
  not tests.
- Cover silent errors and plausible consumer-visible regressions.
- Test documentation must name the wrong behavior that would otherwise pass;
  delete tests that cannot.
- OpenTofu-like declarations use offline `validate`. Test production
  infrastructure with infrastructure tools, not ad hoc scripts.

## Testing machinery

Do not test tests or testing machinery unless that machinery is the shipped
product. This includes tests of checks, lint and static analysis, CI,
selectors and filters, fixtures, fakes, helpers, evaluation harnesses,
graders, judges, and rendered evaluation results.
