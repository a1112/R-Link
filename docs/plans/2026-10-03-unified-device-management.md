# Unified Device Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement unified device inventory and NetBird-backed access management for cloud deployment and supported devices.

**Architecture:** Extend the existing SQLite inventory compatibly with metadata and provider-scoped identities. A lifecycle-owned synchronizer records authenticated NetBird observations; React presents capabilities and official enrollment instructions. Network policies use existing mesh APIs.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, httpx, React, TypeScript, Vitest, pytest.

---

Execute in this session with @superpowers:subagent-driven-development, @superpowers:test-driven-development and an isolated managed worktree. The sibling design contains the detailed API contract.

## Task 1: Backend inventory, synchronization and lifecycle

Files: modify R-Link-Server/core/devices.py, R-Link-Server/api/devices.py, R-Link-Server/main.py and R-Link-Server/conftest.py; create R-Link-Server/core/device_sync.py and R-Link-Server/test_device_management.py.

1. Write failing migration/metadata tests using original SQLite schema and legacy payloads. Example: assert the tags remain ["home"] after a legacy PUT omitting new fields.
2. Run L:/project/R-Link/.venv/Scripts/python.exe -m pytest R-Link-Server/test_device_management.py -q; expect failures for missing behavior.
3. Implement transactional schema migration, strict validation, safe gateways, detail and compatible v1/v2 transfer.
4. Run management/network/inventory-transfer tests; expect all passing.
5. Write failing synchronization tests with httpx.MockTransport: identity, provider switch, stale/error states, metadata preservation, IP revisions, collisions, missing peers, exclusions, revoke failure and shutdown.
6. Implement lifecycle-owned DeviceSync and explicit sync/link/revoke/status/onboarding API. Test environments must not contact live control planes.
7. Run backend tests, commit owned files, obtain specification review, fix/retest, then obtain quality review and fix/retest material findings.

## Task 2: Device management and enrollment UI

Files: modify apps/r-link-web/src/api/devices.ts, apps/r-link-web/src/components/pages/RemoteView.tsx and its tests, apps/r-link-web/src/components/TopologyView.tsx and tests as needed.

1. Write failing interaction tests for metadata, connection status, sync errors/counts, capability gating, gateway choice, enrollment and revoke.
2. Run focused Vitest tests from apps/r-link-web; verify missing behavior failures.
3. Implement optional new TypeScript fields for old fixtures, metadata editing/filtering, polling, honest status and source-aware actions, official installation links and v2 export.
4. Preserve add/search/probe/import/SSH behavior, guard asynchronous actions and confirm revoke. Never claim gateway status proves child health.
5. Run npm test and npm run build; commit owned frontend files.
6. Obtain specification review, then quality review; fix/retest material findings.

## Task 3: Deployment and device installation

Files: create docs/device-management-20261003.md; modify README.md, R-Link-Server/README.md, deploy/.env.example and deploy/compose.yaml.

1. Document existing Compose cloud deployment, NetBird control plane, server-only PAT, desktop/mobile/NAS/router official installation and gateway access.
2. Explain source statuses, route/policy provisioning, explicit revoke, settings, backups and inventory-transfer limits.
3. Wire sync settings through Compose without extra public management ports or secrets.
4. Verify Compose YAML and environment names. Do not claim real hardware/NAT validation.

## Task 4: Verification and integration

1. Run L:/project/R-Link/.venv/Scripts/python.exe -m pytest R-Link-Server -q, npm test, npm run build and relevant migration checks.
2. Request final @superpowers:requesting-code-review against base 4ea9bd5; fix material findings with regression tests and rerun affected checks.
3. Use @superpowers:finishing-a-development-branch and integrate tested changes into the original checkout if it remains unchanged; preserve concurrent user changes otherwise.
4. Do not push/deploy: the user will sync and install. Report verification, the installation document and actual unverified real-device boundaries.
