---
description: Go error handling - never ignore error returns from security-critical operations
languages:
- go
alwaysApply: false
---

# Go Error Handling Security

## Rule
In Go, errors are returned as values and MUST be explicitly checked. Ignoring error returns from security-critical operations can lead to silent failures, undefined behavior, and security vulnerabilities.

## What to Check
- Blank identifier `_` used to discard errors: `result, _ := someFunction()`
- Missing error variable entirely: `result := someFunction()` when function returns `(T, error)`
- Error variable assigned but never checked: `err := someFunction(); // no if err != nil`

## Security-Critical Operations That MUST Check Errors
- Cryptographic operations (cipher creation, encryption, decryption)
- Database operations (connections, queries, scans)
- File operations (open, read, write, close)
- Network operations (listen, accept, read, write)
- Authentication/authorization checks
- Random number generation

## Vulnerability Example
// BAD: Error ignored - cipher might fail silently
block, _ := aes.NewCipher(key)
gcm, _ := cipher.NewGCM(block)

// BAD: Error ignored - query might fail, storedHash is empty string
row.Scan(&storedHash)

// BAD: Error ignored - file might not be written
file, _ := os.Create(path)
file.Write(data)## Secure Example
// GOOD: All errors checked
block, err := aes.NewCipher(key)
if err != nil {
    return nil, fmt.Errorf("failed to create cipher: %w", err)
}

gcm, err := cipher.NewGCM(block)
if err != nil {
    return nil, fmt.Errorf("failed to create GCM: %w", err)
}

// GOOD: Error checked and handled
if err := row.Scan(&storedHash); err != nil {
    if err == sql.ErrNoRows {
        return ErrUserNotFound
    }
    return fmt.Errorf("database error: %w", err)
}## Why This Matters
- Ignored crypto errors → weak/broken encryption
- Ignored database errors → authentication bypass (empty values pass checks)
- Ignored file errors → data loss, incomplete writes
- Ignored random errors → predictable "random" values
