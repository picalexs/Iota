# Public open-source release plan

Status: staging only.

This plan prepares a new public repository for Quantum Simulation Studio. The
staging tree contains application code and the files needed to build, test, and
run the application. It does not contain private Git history, thesis files,
manuscript files, benchmark artifacts, research data, reports, or downloaded
reference material.

## Release decisions

| Decision | Current choice |
| --- | --- |
| Repository | New repository with a new root history. |
| Scope | Application code, tests, runtime configuration, safe scripts, and application documentation. |
| Runtime claim | Local, single-user workbench. The default stack is not a public service. |
| Software license | GNU Affero General Public License, version 3 (AGPL-3.0-only). |
| Owner review | The repository owner reviews every change. |
| Citation file | Not included in this staging scope. |
| Notice file | Not included in this staging scope. Track third-party obligations separately. |

AGPLv3 permits commercial use. It requires covered source changes to keep the
same copyleft freedoms when the work is conveyed. It also requires a modified
network service to offer corresponding source to remote users. This matches the
application's API and web interface.

The AGPL does not automatically apply to a separate program only because that
program communicates with this application. Review the license before linking,
combining, packaging, or deploying other software with this project.

## Definition of done

The public repository is ready only when every condition below is true.

### Scope and history

- [ ] The public repository has a new root commit.
- [ ] The public repository has no imported `.git` directory, old branch, tag,
  remote, pull-request ref, or reflog from the private repository.
- [ ] The tree contains only application code, tests, safe runtime files, and
  reviewed application documentation.
- [ ] Manuscript, thesis, benchmark, research, report, and reference-library
  files are absent.
- [ ] Every included file has an owner and a public-release decision.

### Rights and license

- [ ] `LICENSE` contains the unmodified official GNU AGPLv3 text.
- [ ] README and package metadata identify `AGPL-3.0-only` consistently.
- [ ] Every contributor has permission to license their contribution under the
  AGPL or has an explicit compatible grant.
- [ ] Third-party source, fonts, icons, images, and generated files have a
  recorded license decision before publication.
- [ ] No file claims that commercial use is forbidden. AGPL-covered software
  can be sold or used in a commercial service when its terms are met.

### Privacy and security

- [ ] Secret scans pass on the working tree and the new Git history.
- [ ] No credentials, tokens, private keys, account identifiers, provider job
  identifiers, personal paths, personal emails, or unpublished result data are
  present unless explicitly approved.
- [ ] `.env.example` contains placeholders only and binds local services to
  loopback by default.
- [ ] The README states that the default application has no independent API
  authentication or tenant isolation.
- [ ] Public issue and support templates do not request secrets or sensitive
  data.

### Build and runtime

- [ ] Backend, worker, and frontend dependencies use reviewed lock files.
- [ ] Generated API types are reproducible from the public tree.
- [ ] Backend and worker unit tests pass.
- [ ] Frontend type, lint, test, and build checks pass.
- [ ] `docker compose config --quiet` passes.
- [ ] A rebuilt local Compose stack starts with healthy API, database, Redis,
  worker, and UI services.
- [ ] The UI and API health endpoints return successful responses.
- [ ] A real browser opens the UI, creates or selects a representative local
  run, and reports no application console errors.
- [ ] No real IBM Runtime job runs as part of the release gate.

### Repository controls

- [ ] The default branch requires review from the owner.
- [ ] Required status checks are selected after the first clean CI run.
- [ ] Dependency updates and security reports have an owner.
- [ ] The repository has a security reporting path and a support path.
- [ ] The first public tag identifies the reviewed release tree.

## Guardrails

### History guardrail

Create the public repository from an explicit reviewed file set. Do not clone
the private repository and push its history. Do not use mirror pushes, all-ref
pushes, or tag pushes from the private repository.

Before the first push, verify:

```sh
git rev-list --all --count
git remote -v
git log --all --oneline -5
```

The first command must report only the intended new history. The second must
show no unintended remote. The third must show only public commits.

### Content guardrail

Treat every file as private until reviewed. File names are not proof that a
file is safe. Inspect generated files, fixtures, snapshots, logs, database
exports, Docker configuration, CI settings, and example environment files.

Exclude these classes by default:

- private history and Git metadata;
- credentials, secrets, certificates, and local environment files;
- thesis and manuscript material;
- benchmark archives, event logs, campaign exports, and research results;
- downloaded papers, publisher templates, and reference libraries;
- local database, Redis, coverage, build, cache, and browser output;
- deployment configuration that assumes authentication, tenancy, or secret
  management that the application does not provide.

### Runtime guardrail

Keep the default Compose stack loopback-only. Do not describe it as production
ready or multi-user. Do not expose it to a network without a separate design
for authentication, authorization, tenant isolation, rate limiting, secret
management, logging, and operational recovery.

Keep local simulator results separate from IBM Runtime results. Never treat a
requested backend as proof that a hardware job ran.

### License guardrail

Keep the complete AGPL text at the repository root. Preserve license notices
in copied code. Mark modified files when required by the license. When the web
application runs a modified version, provide remote users a clear source path.

Do not add a noncommercial restriction to AGPL-covered code. If the owner later
wants a separate commercial license for code that the owner solely controls,
make that a separate licensing decision. Do not assume that right applies to
code contributed by another person.

## Execution plan

### Phase 1: Freeze the public boundary

1. Review the inclusion list and remove non-application material.
2. Review source, tests, fixtures, configuration, and generated files.
3. Confirm the owner identity and public contact paths.
4. Record unresolved rights or privacy questions as release blockers.

Stop when a file has an unknown owner, unknown rights, or unresolved sensitive
content.

### Phase 2: Prepare the clean repository

1. Work in the isolated staging directory.
2. Keep the private repository unchanged.
3. Add `LICENSE`, community files, CI policy, and sanitized examples.
4. Remove generated local output.
5. Initialize a new Git repository.
6. Inspect the first staged file list and diff before creating the first commit.

### Phase 3: Run release checks

Run the checks in `docs/testing.md`. Add secret, private-path, credential,
license, and forbidden-file scans. Run the Compose smoke test and the
representative Playwright flow from a clean local state.

Record the command, date, result, and known limitation for each gate. A timeout
or unavailable service is unverified. It is not a pass.

### Phase 4: Review the public diff

Check the staged tree with these questions:

- Does every file belong in an application repository?
- Does any file disclose a private path, identity, credential, or provider
  record?
- Does the README describe only behavior that the tests and code support?
- Do license statements match `LICENSE` and package metadata?
- Can a new contributor build and test the application from the README?
- Can a network user find source for a modified hosted version?

Resolve every finding before the first push.

### Phase 5: Publish and configure

Only after all gates pass:

1. Create the new remote repository with the intended visibility.
2. Add the remote to the new staging repository only.
3. Push the new default branch.
4. Configure owner review, required checks, secret scanning, Dependabot, and
   branch protection.
5. Create the first reviewed release tag.
6. Recheck the public repository from a fresh clone.

Do not connect the new remote to the private repository. Do not push private
branches, tags, or history.

## Stop conditions

Stop the release if any of these conditions occurs:

- a secret or private key is found;
- a file contains unresolved personal or provider data;
- a third-party asset has no confirmed redistribution right;
- the clean repository contains unexpected history or a remote;
- the default runtime can bind outside loopback without an explicit warning;
- a required test or browser check is unverified;
- license ownership or contributor permission is unclear;
- a release claim exceeds the evidence from code and tests.

Record the blocker. Do not push until the blocker is resolved or the affected
file and claim are removed from the release.
