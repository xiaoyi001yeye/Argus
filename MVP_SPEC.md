# Argus MVP specification

## Goal

Complete one reproducible diagnostic loop:

> A user describes a failure, the AI searches an approved log source, requests
> nearby context, and returns an evidence-backed preliminary cause.

Argus retrieves evidence. The connected AI client performs the diagnosis.

## First release boundary

The MVP reads fixed local log files so the tool protocol can be tested without
SSH credentials. The next milestone replaces the provider with an SSH
implementation that reuses OpenSSH configuration and key-based authentication.

Not in the MVP:

- arbitrary remote shell commands;
- user-supplied hosts or file paths;
- password or private-key storage;
- live `tail -f`;
- service restarts or other server mutations;
- multi-host correlation, embeddings, or a standalone agent runtime.

## Tool contract

### `list_log_sources`

Input: configured environment name.

Output: source identifiers and descriptions. Physical paths are not returned.

### `search_logs`

Input: source identifier, optional ISO-8601 time range, a plain-text query, and
a bounded result limit.

The query supports case-insensitive terms separated by `OR`. It is not a shell
expression or regular expression.

Output: timestamp, level, redacted message, source identifier, and an opaque
cursor for every match, plus a truncation flag.

### `get_log_context`

Input: source identifier, cursor returned by `search_logs`, and bounded line
counts before and after the match.

Output: redacted surrounding lines. A cursor is valid only for the source that
created it.

## Security constraints

- Environments and sources are loaded from an operator-owned allow list.
- The MCP caller cannot specify a host, filesystem path, or shell fragment.
- Requested limits and context windows are capped.
- Reads have a configurable maximum file size and timeout budget.
- Returned lines have a configurable maximum length.
- Common password, token, authorization, and API-key patterns are redacted.
- SSH must use argument arrays or an SSH library, never `shell=True`.
- The server is read-only and never changes a remote system.

## Configuration

```yaml
environments:
  local:
    provider: local
    log_sources:
      order-service:
        path: fixtures/order-service.log
        description: Order service application log
```

A future SSH environment will add an SSH alias (resolved by
`~/.ssh/config`) while preserving the same logical source identifiers.

## Acceptance scenario

Given the included order-service fixture, a client investigating a failed order
must be able to:

1. list `order-service`;
2. find the database timeout error;
3. retrieve its preceding and following context;
4. cite the time and direct error;
5. state explicitly that the deeper root cause is unknown if the evidence does
   not prove it.
