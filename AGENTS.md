# Repository agent rules

These rules apply to all files in this repository. A more specific `AGENTS.md` file can add rules for its scope.

## Design and change rules

- Organize code by domain or feature. Do not organize code only by technical layer.
- Make dependencies explicit in imports, function parameters, and public contracts.
- Do not depend on hidden global state, import side effects, or call order.
- Define each business rule in one owning location. Reuse that rule instead of copying it.
- Extract similar code only when the behavior, ownership, and lifecycle are the same.
- Use types and models that cannot represent invalid combinations of state when practical.
- Give each file and module one reason to change.
- Follow the dependency direction defined by the nearest scoped `AGENTS.md` file.
- Use a module's public boundary from outside that module.
- Do not bypass a public boundary to import private implementation code.
- Do not add a wrapper that only forwards arguments and return values.
- Validate untrusted input at the first external boundary.
- Translate internal errors to protocol or user-facing errors at the boundary.

