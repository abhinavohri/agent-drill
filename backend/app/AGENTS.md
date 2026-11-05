# Application module rules

These rules apply to all files in `backend/app/`.

## Public boundaries

- Use `app/<domain>/facade.py` as the only public interface of a domain.
- Put implementation files in `app/<domain>/internal/`.
- Import another domain with `from app.<domain>.facade import ...`.
- Do not import `app.<other-domain>.internal`.
- Keep facade exports explicit.
- Do not put business logic in a facade.

## Internal imports

- Import the current domain's internal files directly.
- Do not route an internal import through the current domain's facade.
- Keep dependency direction acyclic.
- Move shared behavior to its owning domain.

## Composition

- `app/main.py` can import domain facades.
- `app/jobs/` can import domain facades.
- Composition code must not import a domain's internal package.
- Keep route registration in the owning domain facade.

## Models

- Put shared domain models in a focused `models.py` file inside the owning domain.
- Put route request and response models in the owning route schema file.
- Put provider response models with the provider.
- Keep model names specific to the business concept.
- Do not pass an unvalidated provider dictionary beyond the provider boundary.

