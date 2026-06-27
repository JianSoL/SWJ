# Design QA

- Source visual truth: `C:\Users\ch\AppData\Local\Temp\codex-clipboard-289d3f5e-ba01-4547-943f-5e5e371b6da3.png`
- Implementation screenshot: `D:\DDSAVE\工作\AIDCSWJ\build\layout_audit\cell_3d_perspective_1480x840.png`
- Viewport: 1480 x 840
- State: compiled cluster, voltage chart selected, populated 6-module data set

**Full-View Comparison Evidence**

- Both views use a white plotting surface, perspective 3D bar matrix, receding grid, low-to-high blue/yellow/red scale, vertical colorbar, and generous inspection space around the chart.
- The implementation intentionally retains the AIDC application header, current-cluster context, voltage/temperature tabs, statistics, and chart navigation toolbar around the referenced chart treatment.

**Focused Region Comparison Evidence**

- No separate crop was required: at 1480 x 840 the bar faces, perspective grid, three axes, tick labels, colorbar, and plot spacing are readable in the full-view comparison.

**Required Fidelity Surfaces**

- Fonts and typography: AIDC controls retain Microsoft YaHei UI; chart labels prefer Microsoft YaHei/SimHei with DejaVu Sans fallback. Sizes and weights remain legible without crowding.
- Spacing and layout rhythm: chart occupies the available page height, leaves rotation space, and does not overlap the summary, tabs, axes, colorbar, or toolbar at the target viewport.
- Colors and visual tokens: chart follows the reference's cool-low/warm-high progression while preserving the application's restrained white and gray surface palette.
- Image quality and asset fidelity: the chart is rendered natively at the current DPI, so bars, grid lines, and labels remain sharp while resizing. No placeholder or approximated raster asset is used.
- Copy and content: axes use product-specific labels for cell number, module, voltage, and temperature; statistics and units reflect live protocol data.

**Findings**

- No actionable P0, P1, or P2 differences remain.
- P3: the native Matplotlib navigation toolbar is visible below the chart; this is retained because it provides rotation reset, pan, zoom, and export controls required for the delivered desktop workflow.

**Patches Made Since Previous QA Pass**

- Replaced the interim heatmap with native interactive 3D bar charts.
- Moved the continuous colorbar to the left to match the reference composition.
- Added perspective projection with stronger focal depth and a lower oblique camera angle.
- Enlarged the plot box and preserved the user's camera angle across live data refreshes.
- Throttled redraws and cancelled pending paint work during shutdown.

**Implementation Checklist**

- [x] Voltage and temperature chart switching
- [x] Perspective rotation and wheel zoom
- [x] Live current-cluster data binding
- [x] Missing-value handling and protocol scaling
- [x] Responsive 1366 x 768 and 1920 x 1080 rendering
- [x] Empty and uncompiled-cluster states

## Header Redesign QA

- Defect evidence: `C:\Users\ch\AppData\Local\Temp\codex-clipboard-0433065d-f875-4236-96a5-5d468fae4afa.png`
- Implementation screenshot: `D:\DDSAVE\工作\AIDCSWJ\build\layout_audit\header_widget_corrected_1415.png`
- Viewport width: 1415 px
- State: disconnected CAN, first compiled cluster selected, logging disabled

The original single row mixes connection, system, factory, and logging controls and pushes later states beyond the visible region. The revised header separates connection and receive status from system, factory, and logging actions; both rows use centered control baselines and remain fully visible. The brand block is capped at 220 px, header height falls to 87 px, and the command area gains a predictable left-to-right scan order.

- Fonts and typography: captions use a consistent 12 px weight and align vertically with their associated controls.
- Spacing and layout: both command rows use 7 px horizontal spacing and a 6 px row gap; no overlap was found from 1024 x 640 through 1920 x 1080.
- Colors and tokens: primary, warning, success, and neutral states continue using the existing release theme.
- Copy and content: every original command and status remains available; only grouping and order changed.
- Accessibility: the tighter layout preserves existing tooltips and minimum control heights. Keyboard and screen-reader behavior still depends on the native Qt controls.

No actionable P0, P1, or P2 header findings remain.

## System K-Line QA

- Source visual truth: `C:\Users\ch\AppData\Local\Temp\codex-clipboard-f63d20c1-1b1d-47da-a570-21a3d7751605.png`
- Implementation screenshot: `D:\DDSAVE\工作\AIDCSWJ\build\layout_audit\system_kline_main_1366x768.png`
- Target states: total voltage and signed current, populated compiled cluster, 5-second period, 120-bar window
- Responsive viewports: 1366 x 768 and 1920 x 1080

The implementation carries over the reference's K-line geometry while using BMS sampling terms throughout: period-first value, period maximum, period minimum, latest value, and five-period average. A rise from the period-first value is red and a fall is green. Financial-only close-price, MACD, and trade annotations are intentionally omitted; the lower panel reports CAN sample count per period, which is meaningful for equipment diagnostics.

- Data fidelity: voltage index 13 is scaled to 0.1 V; current index 14 is decoded as signed 16-bit and scaled to 0.1 A.
- Isolation: raw samples and aggregated bars are stored per cluster. Selecting 00 displays an empty state without deleting compiled-cluster history.
- Controls: 1/5/10/30/60-second periods, 60/120/240-bar windows, pause-with-background-capture, current-cluster clear, pan, zoom, reset, and image export.
- Refresh behavior: total voltage and current are shared signals polled and cached in the background on every application page. They are removed from page-specific monitor and cluster queues to prevent duplicate requests; all-cluster logging only supplements non-active clusters. Successful responses feed the per-cluster history directly, failed responses are ignored, and visible-canvas redraw is throttled to 320 ms without restarting an active redraw deadline.
- Layout: native Qt controls stay on one compact row while the chart consumes remaining height. No overlap was found at the tested laptop and desktop sizes.

No actionable P0, P1, or P2 K-line findings remain.

final result: passed
