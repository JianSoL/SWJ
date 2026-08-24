# Design QA: 全簇运行大屏模板改版

## Evidence

- Source visual truth: `C:\Users\ch\.codex\generated_images\019fe979-e3dc-7c63-b520-0ed13f0e1d15\exec-e2655610-ddb1-4091-b152-68c958d91e56.png`
- Implementation screenshot: `docs/screenshots/cluster_dashboard_implementation.png`
- Same-input comparison: `docs/screenshots/cluster_dashboard_comparison.png`
- Capture helper: `scripts/capture_cluster_dashboard.py`
- Source pixels: `1487 x 1058`; implementation pixels: `1487 x 1058`
- Native viewport: `1487 x 1058` device-independent pixels at device pixel ratio `1.0`; no density normalization was required.
- State: light theme, 16 clusters, abnormal-first enabled, one offline cluster, alarm/warning/normal states populated, fullscreen control visible.
- Runtime: native PySide/PyQt-compatible Qt desktop UI captured with `QT_QPA_PLATFORM=offscreen`; Microsoft YaHei was loaded for deterministic Chinese rendering.

## Findings

- No actionable P0, P1, or P2 differences remain in the dashboard content area.
- The existing application header and product-specific tabs intentionally differ from the concept image because they are shared, working DCBMS navigation rather than homepage-only decoration.
- Two extra table columns, `最高单体(mV)` and `最低单体(mV)`, intentionally extend the template to satisfy the product requirement.

## Fidelity surfaces

| Surface | Result | Evidence |
| --- | --- | --- |
| Fonts and typography | Passed | Microsoft YaHei UI, compact 12–23 px hierarchy, bold page/table headings, and non-wrapping dense values match the industrial dashboard character without truncation. |
| Spacing and layout rhythm | Passed | Title, five equal summary cards, and the single full-width table follow the source composition; margins, 8 px radii, 42 px rows, and table density remain readable at the reference viewport. |
| Colors and visual tokens | Passed | White cards, blue active controls, pale blue page background, green/amber/red/gray states, subtle borders, and restrained selected/abnormal row fills match the source palette. |
| Image and icon quality | Passed | The source contains no photos or illustrations. Qt's standard icon library supplies crisp, native summary and communication icons; no placeholder, emoji, or handcrafted image asset is used. |
| Copy and content | Passed | Title, hint, summary labels, table labels, alarm text, timestamps, and status terminology are product-specific Chinese copy. Maximum and minimum cell voltage remain visible as requested. |

## Full-view and focused evidence

- Full-view comparison confirms the same title → summary cards → fleet table hierarchy and comparable information density.
- Dense table values, state badges, SOC bars, switch thumb, headers, and timestamps remain readable in the original-resolution combined comparison, so a separate enlarged crop was not needed.

## Comparison history

1. First template pass replaced the legacy chart/detail layout with summary cards and a fleet table. Comparison found clipped communication badges, a switch without a clear thumb, and the offline row below normal rows despite `异常优先` being enabled (P2).
2. Communication and run-state columns received stable widths; the abnormal control became a real two-state slider; abnormal sorting changed to offline → alarm → warning → unknown → normal; automatic row selection was removed.
3. The revised same-viewport capture shows complete communication labels, an unambiguous switch, offline-first ordering, no horizontal clipping, and all required voltage-extrema columns.

## Interaction verification

- Clicking a fleet row emits the selected cluster and opens realtime monitoring through the existing MainWindow service flow.
- Abnormal-first sorting remains interactive.
- Fullscreen hides the product header and complete tab bar without leaving layout space; the button and `Esc` restore them.
- Focused Qt tests: 5 passed after the final layout iteration.
- Full regression: 176 tests passed in 60.519 seconds.
- Browser console verification is not applicable because this is a native Qt desktop application, not a browser route.

## Follow-up polish

- P3: the shared product header can be restyled in a separate application-wide pass if every page should adopt the concept image's exact two-row chrome.

final result: passed
