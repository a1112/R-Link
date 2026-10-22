# Topology interaction implementation plan

**Goal:** Fulfil the browser comment requesting complete zoom, drag, select and edit interactions on the approved topology home.

**Design:** Retain the existing visual style and real service data. Replace scroll-bound movement with a camera transform, cursor-anchored wheel zoom, touch pinch and free panning. Nodes (including the context hub) can be dragged; Shift/Ctrl selection and an explicit box-selection tool move groups together. Selection opens real details; registered-device editing uses the existing API form. Local display aliases and notes are explicitly marked local and do not modify R-File or device connectivity. Persist positions/annotations per configured service, with bounded undo/redo and restore-layout controls. Preserve keyboard navigation and isolated polling errors.

**Implementation:**
1. Add geometry/storage unit regressions for anchored zoom, fit, rectangle selection, malformed saved data and service isolation. Confirm RED; implement interaction.ts and useTopologyDocument.ts.
2. Add interaction tests for pointer pan/node drag, multi-selection, cancel, wheel/pinch, keyboard, undo/redo, annotations and existing device editing. Confirm RED; build TopologyCanvas.tsx and integrate TopologyView/details/CSS.
3. Run the frontend/window suites and production build; use browser QA on actual data and isolated fixtures at desktop/mobile widths. Request independent review, resolve findings, and update the local preview and Windows client. No cloud publish is implied by this UI request.

Validation: 137 frontend tests in 26 files, 12 desktop-window tests, TypeScript and production build passed. Independent review fixes preserve native Space activation on buttons; editing uses explicit toolbar/detail buttons and F2. Real browser QA verified free panning, wheel zoom, node and three-node group dragging, box selection, keyboard undo, scoped annotation persistence across reload, and the 601x670 edit dialog. Two-finger gesture logic is covered by pointer-event tests. Test inventory runs on a separate read-only fixture server, never in production inventory. The existing chunk-size build warning remains.
