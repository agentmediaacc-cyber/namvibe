# Dating Architecture

Dating is implemented as a layered feature over the shared NamVibe profile, notification, messaging, media, and blocking systems.

- Discovery: real profile rows plus eligibility filters
- Compatibility: deterministic scoring from explicit profile data only
- Match lifecycle: like -> reciprocal like -> one active match
- Messaging: reuses the canonical thread model
- Safety: blocks and reports override ranking and matching
- UI: premium templates and one JS controller

## Cache / invalidation
Personalized results are not cached under public keys. Discovery and matches depend on profile, preference, like, pass, block, and pause state.
