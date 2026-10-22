# Topology Home Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the approved topology-home visual with actual device states, selection/details and existing device actions.

**Architecture:** Keep the existing React application and authenticated APIs. Replace TopologyView with an accessible HTML-node/SVG-edge canvas, backed independently by the registered inventory and R-File network inventory. Use real gateway relationships where available; other edges describe management/discovery, not invented VPN tunnels. Keep current-server context separate from device totals.

**Tech Stack:** React 18, TypeScript, existing Lucide icons, CSS, Vitest/Testing Library, Vite/Tauri. No new dependencies.

Approved reference: docs/designs/r-link-topology-home-v1.png. User approved implementation on 2026-10-04. Retain all existing management routes, SSH session lifetime, service switching and settings. Show no sample devices in production. Unknown data stays unknown; TCP reachability, gateway availability and device presence are distinct. R-File peer information has no SSH target or per-peer filesystem scope, so its detail action opens the existing R-File service page.

## Task 1 — Topology data and behavior

Files: create src/components/topology/model.ts and model.test.ts under apps/r-link-web; replace TopologyView.test.tsx and TopologyView.tsx; create topology/TopologyDetails.tsx and topology/topology.css.

1. Add failing tests for state classification, stable unique IDs, gateway edges, filtering, honest R-File status and revoked access.
2. Run `npx vitest run src/components/topology/model.test.ts --pool threads --maxWorkers 1 --no-file-parallelism`; confirm missing implementation failure.
3. Implement normalized nodes and deterministic collision-free columns/rows. Registered gateway edges use gateway_id; management/discovery edges are visibly distinct from physical network claims. Search and source/type/status filters apply to all sources; offscreen parent fallback must retain truthful edge semantics.
4. Add failing interaction tests: selecting/closing details, status counts, safe existing SSH/Web actions, R-File navigation, errors clear stale nodes, refresh updates selection/removal, empty inventory, zoom bounds/reset and keyboard access.
5. Implement the dark dotted canvas, device icons, selected blue border/edge, responsive detail panel, zoom/pan/fit controls, and independently polled source errors. Use semantic buttons and a labelled nonmodal detail region with focus restoration.
6. Run model and topology tests until passing; commit the component and tests.

## Task 2 — Home navigation and management handoff

Files: App.tsx/App.test.tsx; constants/routes.ts; components/layout/Sidebar.tsx and MainLayout.tsx; components/common/SidebarItem.tsx; pages/RemoteView.tsx/RemoteView.test.tsx.

1. Change App tests to require topology on first launch and verify SSH sessions survive navigation. Add tests for add/edit requests opening the actual inventory form without reopening on polling.
2. Verify RED with targeted tests, then make network the default route, move topology first, style the sidebar's active item blue, and retain the old dashboard as system overview. Pass specific add/edit requests to RemoteView and preserve safe SSH target routing.
3. Give topology a viewport-filling layout and a narrow-screen stacked details layout. Existing pages retain their normal scrolling/padding.
4. Run targeted tests, then full frontend suite, window-chrome tests, typecheck/build. Commit when green.

## Task 3 — Review and delivery

1. Inspect a real running browser preview with actual local APIs and controlled test fixtures for online/offline/unknown and selected details; clearly label fixture-only validation, never seed production inventory. Check desktop and narrow viewport, scrolling, keyboard selection, no overlap and no console errors.
2. Request independent code review using superpowers:requesting-code-review; address actionable findings and rerun affected checks.
3. Integrate the reviewed branch into the primary checkout without overwriting unrelated changes. Preserve preview evidence and build output outside temporary worktrees, open the updated preview, and report verification and any remaining native-build/deployment limits accurately.

## Verification — 2026-10-04

Implemented the approved design as the default home, using real registered and R-File inventories, source-isolated polling, truthful management/gateway edges, searchable status/type/source filters, accessible selection/details and existing SSH/Web/edit/add handoffs. No production sample records or new dependencies were added.

Validation: 126 frontend tests across 24 files; 12 desktop-window tests; TypeScript and production build passed. Independent review found no blocking issue; its slow-source loading suggestion was fixed with a regression test. Browser QA covered the actual local backend (one R-File peer, no registered devices), a separate read-only seven-device fixture server, selected NAS details, edit handoff, and 390px mobile layout. Small inventories fit their actual bounds; mobile cards retain readable zoom and selecting a device scrolls to details. Screenshots are preserved locally under `.repository-consolidation-local/topology-qa/` and clearly mark fixture data. The existing large frontend chunk build warning remains.
