# Contributing to RetailOps ML

Thank you for improving RetailOps ML. This project is a governed
decision-support system: changes must preserve evidence, authorisation, and
human-review boundaries.

## Before you start

- Read the [product constitution](docs/constitution.md), relevant connector or
  lifecycle contract, and [reuse guide](docs/reuse-guide.md).
- Work only with labelled fixtures or explicitly documented public benchmark
  material. Do not commit customer data, credentials, or sensitive exports.
- Keep the product within its boundary: it may support a human planner, but it
  may not execute purchasing, transfers, pricing, or supplier contact.

## Local verification

Install the backend and frontend prerequisites described in the README, then
run:

```powershell
.\scripts\verify.ps1
```

Or on macOS/Linux:

```bash
./scripts/verify.sh
```

The command runs the Python test suite and frontend production build. CI runs
the same checks for pull requests and changes to `main`.

## Change requirements

| Change | Required evidence |
| --- | --- |
| Connector or data contract | Explicit authorisation boundary, success/failure/safety tests, versioned snapshot metadata |
| Model, feature, or threshold | Chronological validation, declared baseline, locked final-test integrity, rollback path |
| Specialist or policy contract | Deterministic fixture tests including an inconclusive or rejection path |
| API contract | Route-level success and failure tests, backwards-compatibility review |
| UI claim or demo | Visible source-mode label and no unsupported customer or impact claim |

## Pull request checklist

- [ ] Scope and source mode are stated in the pull request.
- [ ] No secrets, customer data, or hidden operational logic are included.
- [ ] Relevant tests and `scripts/verify` pass locally.
- [ ] Documentation and fixtures reflect the changed contract.
- [ ] The change fails closed when required evidence is absent.
- [ ] Any forecast or policy change retains human approval and rollback.

## Style

Use the repository `.editorconfig`. Keep Python, TypeScript, and documentation
changes focused, readable, and covered by the smallest useful tests. Avoid
adding tooling that is not executed by local verification or CI.
