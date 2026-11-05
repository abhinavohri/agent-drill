# Repository agent rules

These rules apply to all files in this repository.

## Rule hierarchy and maintenance

- Apply this root file to the complete repository. A nested `AGENTS.md` inherits it and applies only to its directory and descendants.
- Keep each rule in one file at the highest scope that fully owns it. A nested file adds only scope-specific details and does not restate a parent rule.
- Override a parent rule only when the nested file names the parent rule, gives the reason, and defines the exact scope.
- When two repository rules conflict without an explicit override, stop, report the conflict, and resolve it in the owning rule files before making the change.
- Review affected nested files when a parent rule changes, and update or remove rules that no longer apply.
- Add a rule only when a repeated review issue shows that the current rules are incomplete.

## Design and change rules

- Organize code by domain or feature, and give each file and module one reason to change.
- Keep each production source file at 250 lines or fewer. Split it by feature responsibility before it exceeds this limit.
- Keep test files at 350 lines or fewer. Generated files and data fixtures are exempt.
- Make dependencies explicit in imports, function parameters, and public contracts. Do not depend on hidden global state, import side effects, or call order.
- Define each business rule in one owning location. Reuse that rule instead of copying it.
- Extract similar code only when the behavior, ownership, and lifecycle are the same.
- Use a typed model for each fixed data shape. Do not use a dictionary, list, or tuple as an anonymous record.
- Model lifecycle states with one model and a status enum when they share one identity and most fields. Use separate models or a discriminated union when states require materially different data or expose different operations, especially in public contracts.
- Make a field optional only when absence is a valid domain state. Do not use `None` to represent an unvalidated or incomplete object.
- Follow the dependency direction defined by the nearest scoped `AGENTS.md` file, and cross a module boundary only through its public interface.
- Do not add a wrapper that only forwards arguments and return values.
- Validate untrusted input once at the first boundary that knows its complete contract, then pass validated types through internal code without repeating identical validation.
- Validate again only at a new trust boundary, at a stronger contract boundary, or for a rule that depends on current domain state. Keep state-dependent rules in the domain that owns the state.
- Use internal assertions for invariants that types cannot express. Do not use assertions to validate external input.
- Translate internal errors to protocol or user-facing errors at the boundary.
- Search callers, tests, configuration, and exports before moving or deleting code.

