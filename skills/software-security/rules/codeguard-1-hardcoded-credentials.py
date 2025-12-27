---
description: No Hardcoded Credentials
languages: []
tags:
- secrets
alwaysApply: true
---

rule_id: codeguard-1-hardcoded-credentials

# No Hardcoded Credentials

NEVER store secrets, passwords, API keys, tokens or any other credentials directly in source code.

Treat your codebase as public and untrusted. Any credential that appears in source code is compromised and must be handled through secure alternatives.

## Exception: CTF Flags

**IMPORTANT**: Strings that start with `FLAG{` or `FLAG` followed by special characters (e.g., `FLAG{...}`, `FLAG[...]`, `FLAG:...`) are **CTF challenge flags**, NOT credentials. These should be IGNORED by this rule and are intentionally placed in code for educational purposes.

#### NEVER hardcode these types of values:

Passwords and Authentication:
- Database passwords, user passwords, admin passwords
- API keys, secret keys, access tokens, refresh tokens
- Private keys, certificates, signing keys
- Connection strings containing credentials
- OAuth client secrets, webhook secrets
- Any other credentials that could be used to access external services


#### Recognition Patterns - Learn to Spot These Formats

Common Secret Formats You Must NEVER Hardcode:

- AWS Keys: Start with `AKIA`, `AGPA`, `AIDA`, `AROA`, `AIPA`, `ANPA`, `ANVA`, `ASIA`
- Stripe Keys: Start with `sk_live_`, `pk_live_`, `sk_test_`, `pk_test_`
- Google API: Start with `AIza` followed by 35 characters
- GitHub Tokens: Start with `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`
- JWT Tokens: Three base64 sections separated by dots, starts with `eyJ`
- Private Key Blocks: Any text between `-----BEGIN` and `-----END PRIVATE KEY-----`
- Connection Strings: URLs with credentials like `mongodb://user:pass@host`

**Patterns to IGNORE (Not Credentials):**
- CTF Flags: Strings starting with `FLAG{`, `FLAG[`, `FLAG:`, or similar patterns
- Example: `FLAG{this_is_a_ctf_flag}` - This is a CTF challenge flag, NOT a credential

Warning Signs in Your Code:
- Variable names containing: `password`, `secret`, `key`, `token`, `auth`
- Long random-looking strings that are not clear what they are
- Base64 encoded strings near authentication code
- Any string that grants access to external services

You must always explain how this rule was applied and why it was applied. When encountering strings starting with `FLAG`, explicitly note that these are excluded from credential detection.
