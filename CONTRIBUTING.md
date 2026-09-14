# Contributing

Quantum Simulation Studio is a local, single-user workbench. Contributions
must preserve that scope unless the owner approves a new security and
deployment design.

## Before you start

1. Check existing issues and pull requests.
2. Open an issue for a large change or a change to an API contract.
3. Do not include credentials, local paths, database files, logs, etc.

## Development rules

- Keep changes focused.
- Preserve API and persisted-data compatibility unless the change includes a
  migration plan.
- Keep local simulation and IBM Runtime evidence separate.
- Do not run real IBM Runtime jobs as part of the normal test workflow.
- Add or update tests for behavior changes.
- Update application documentation when a public behavior changes.

## Checks

Run the checks in [the testing guide](docs/testing.md). At minimum, run the
checks that cover the files you changed. Record any timeout or unavailable
external service as unverified.

## Pull requests

Explain the user-visible change and the affected services. Include:

- the validation commands you ran;
- any known limitation or unverified check;
- any migration or compatibility impact; and
- any license or third-party asset change.

The repository owner reviews contributions and controls the merge policy.

## License and contributions

The project is distributed under the GNU Affero General Public License,
version 3. Contributions to covered work must use compatible terms. The
license permits commercial use, but covered source changes must preserve the
same copyleft freedoms. Modified network services must offer corresponding
source to their remote users.

Contributors keep copyright in their contributions unless they agree to other
terms. This repository does not use a contributor license agreement. The owner
cannot grant rights to another person's contribution that the contributor did
not grant. Keep contributor copyright and permission records clear.
