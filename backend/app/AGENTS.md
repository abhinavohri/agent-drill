# Application module rules

These rules apply to all files in `backend/app/`.

## Domain packages

- Add code to an existing domain before you create a new domain.
- Give each domain package a name that describes its business purpose.
- Use `app/<domain>/facade.py` as the public interface and `app/<domain>/internal/` for private implementation.
- Import another domain only through its facade. Do not import another domain's internal package.
- Keep facade exports explicit, and add an export only when another domain needs it.
- Do not put business logic in a facade.
- Import the current domain's internal files directly instead of routing the import through its facade.
- Keep dependency direction acyclic.
- Move shared behavior to its owning domain.

## Responsibilities

- A route owns HTTP request and response mapping.
- A facade owns the public operations and types of one domain.
- An internal service owns business logic.
- A provider client owns one external API or protocol contract.
- A parser converts one untrusted source format into validated application data.

## Composition

- Keep `app/main.py` limited to application assembly and process lifecycle work.
- Keep `app/jobs/` as the stable process-entry package unless the task includes a deployment change.
- Composition code can import domain facades but must not import a domain's internal package.
- Keep route registration in the owning domain facade.

## Models

- Use a Pydantic model for HTTP input, HTTP output, provider responses, and stable workflow contracts.
- Use a dataclass for typed internal state that does not need runtime validation or serialization.
- Use a dictionary only for dynamic key sets, opaque protocol data, or immediate wire serialization. Convert known event payloads, tool arguments, tool results, state changes, and other fixed-shape protocol data to typed models before business logic uses them.
- Put shared domain models in a focused `models.py` file inside the owning domain.
- Put route models in the owning route schema file and provider response models with the provider.
- Keep model names specific to the business concept.
- At the route, provider, parser, or protocol boundary that owns the complete contract, validate and normalize required fields, nullability, types, formats, and value bounds before business logic runs.
- Add a focused test for new branching, parsing, identity matching, transition, or policy logic.

