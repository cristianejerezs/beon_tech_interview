# Authenticated accessibility review

**Status: PARTIAL; T062/T075 remain open.**

2026-10-17: exercised the real Streamlit UI in the integrated Chromium browser on an
isolated loopback server, with synthetic identity, provider stub, report, and separate
temporary database. No live model request, real account, or production record was used.

Observed:

- Development sign-in activated using keyboard Enter.
- Question field exposed accessible name `Question`; keyboard text entry worked.
- Generate report activated by Enter and presented report/definition/limitation text.
- Generate button had `:focus-visible` and a nonzero focus box shadow.
- Sharing expander and create-copy button were activated by keyboard.
- Reuse switch exposed its purpose as an accessible name; Space disabled system-improvement
  reuse, and the UI displayed `Off` text, not just a color.
- FAQ expander/button were keyboard-activated; selecting then submitting a FAQ retained a
  non-empty question and generated the synthetic report.
- PDF and CSV controls exposed explicit names. The browser download-event check timed out;
  actual keyboard download completion is **not verified**.
- FAQ JSON viewers exposed clickable tree toggles as unnamed generic elements. Replaced them
  with noninteractive labelled definition/scope tables to avoid requiring those controls.

Remaining before sign-off:

1. Verify real OIDC sign-in and keyboard-only traversal without locator-driven focus.
2. Verify every provider/tracing toggle, history selection, refinement, deletion and
   both downloads, plus supporting-route downloads on a connectivity report.
3. Inspect visible focus throughout, chart/table keyboard interaction, and screen-reader
   announcements for success, clarification, empty, validation and provider-error states.
4. Confirm the PDF/CSV downloads complete and report any browser download limitations.
5. Rerun the full automated suite and record browser/environment/version and final findings.

The automated AppTest coverage checks labels and text status, not browser focus or complete
WCAG conformance. No accessibility pass is inferred from native widgets or these partial checks.
