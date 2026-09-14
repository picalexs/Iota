# Documentation

These documents describe the application in this repository. They do not
describe thesis files, benchmark releases, research results, or deployment as a
public service.

## Application documentation

| Document | Use it for |
| --- | --- |
| [Application walkthrough](app-walkthrough.md) | Main user flow and application capabilities. |
| [Runtime architecture](architecture.md) | Service boundaries and request flow. |
| [Data model](data-model.md) | Database tables and migration behavior. |
| [Frontend](frontend.md) | Frontend structure, routes, and UI ownership. |
| [API endpoints](api-endpoints.md) | REST and Server-Sent Events endpoints. |
| [Pydantic schemas](schemas.md) | API request and response models. |
| [Worker and queue](worker-and-queue.md) | Worker execution and Redis/RQ behavior. |
| [Public release plan](open-source-public-release-plan.md) | License, security, scope, and publication gates. |

## Scope rules

- Keep links relative to this repository.
- Update application documentation when API or runtime behavior changes.
- Do not add private paths, credentials, provider job identifiers, or local
  result exports.
- Do not describe local simulation as hardware evidence.
- Keep publication planning separate from benchmark and manuscript material.
