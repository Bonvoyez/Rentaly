# Rentaly Frontend Design Contract

## 1. Product direction

Rentaly is a calm, operational inspection product. The visual contract is the supplied Figma file (`OV07HgOqCLwTDVoo7ef3ea`): bright white surfaces, Toss-like blue actions, restrained status color, dense but readable admin data, and a fixed appliance canvas for the kiosk.

The admin login adds one project-specific signature moment: an original translucent blue/lilac 3D ribbon knot on the primary panel. It echoes the supplied reference image without copying it and remains decorative (`alt=""`).

Primary users are (1) a borrower returning a board on a 7-inch touch display, (2) an administrator reviewing uncertain inspections, and (3) an operator recovering from device or authentication errors.

## 2. Foundations

- Font: `Noto Sans KR`, fallback `Arial`, `sans-serif`.
- Primary: `#3182F6`; primary soft: `#EDF5FF`.
- Text: `#191F28`; secondary text: `#4E5968`; muted: `#8B95A2`.
- Background: `#F7F8FA`; surface: `#FFFFFF`; border: `#D6DEE8`; subtle border: `#E5E8EC`.
- Dark mode: neutral charcoal canvas `#17181C`, sidebar `#1B1C21`, content `#202127`, elevated card `#292B31`, hover `#30333B`, border `#3B3D46`, strong control border `#4A4D57`, text `#F1F2F4`, secondary text `#B4B7C1`. Blue stays an action accent; status colors use muted translucent fills. Surface levels and text contrast take priority over saturated navy backgrounds.
- Success: `#20C997`; success soft: `#E8FAF4`.
- Warning: `#FFB020`; warning soft: `#FFF7E5`; warning text: `#D08400`.
- Error: `#F04452`; error soft: `#FFF0F2`.
- Spacing follows an 8px grid with 4px half steps. Kiosk safe padding is 24px.
- Radius: canvas 22px, card 16px, control 10-14px, pill 999px.
- Typography: kiosk title 28/1.35 bold; admin page title 28/1.35 bold; modal title 24/1.4 bold; body 14/1.55; label/table 12-13px.

## 3. Layout contracts

- Kiosk is a fixed `800 × 480` canvas. It scales down uniformly when the viewport is smaller and never scrolls internally. Figma nodes: `18:6`, `18:23`, `18:44`, `203:94`, `18:79`, `18:98`, `18:164`, `107:52`, `107:70`, `199:909`.
- Admin targets `1440 × 900`. Sidebar is 220px; content starts at x=260px and is 1140px wide. The page may scroll below 900px but the reference viewport itself must not clip. Figma nodes: `19:18`, `19:36`, `19:133`, `19:193`, `24:46`, `24:68`, `24:91`, `24:105`, `24:215`, `24:317`, `24:421`, `24:483`, `45:195`, `45:223`, `57:49`, `57:155`.
- Admin shell uses the fixed-sidenav pattern: the sidebar remains fixed within the 900px frame and the main region owns vertical scrolling. Inspection history, device management, and detail views share the same shell.
- At narrow admin widths, the header uses one brand row, one equal-width navigation row, and one equal-width utility row. Tables become mobile cards; controls keep a consistent 40px touch height without page-level horizontal scrolling.

## 4. Interaction and motion

- Primary kiosk actions are 240 × 56px. All interactive targets are at least 48px on kiosk and 40px on admin.
- Hover changes color only for actionable desktop controls. Focus uses a 3px primary outline with 2px offset.
- Dialogs trap intent visually, close on Cancel or Escape, and return focus to the trigger.
- Theme selection is user-controlled, persists in `localStorage`, and applies through a root `.dark` class. The initial theme follows the stored choice, then the operating-system preference.
- Motion is limited to progress width, dialog opacity/transform, and completion transitions. Respect `prefers-reduced-motion`.
- The kiosk demo controller exposes every Figma state; telemetry can replace it through the service boundary without changing page components.

## 5. Reusable primitives and states

- `Button`: primary, secondary, disabled; kiosk and admin sizes.
- `StatusBadge`: pass/success, fail/pending/warning, error, neutral.
- `SystemStatus`: connected and disconnected.
- `ProgressBar`: 0-100 with an optional current-stage label.
- `TextField`: default, focus, password, error.
- `Card`: metric, image, detail, inspection check.
- `SelectMenu`: closed, open, selected, clearable filter chip.
- `DataTable`: populated and empty.
- `Dialog`: confirm pass and confirm reject.
- `InspectionCheck`: success, active, warning, error, not-applicable.
- `ThemeToggle`: explicit light/dark switch with text label and icon.
- `Pagination`: previous, numbered pages, next, disabled boundary states, and an accessible current-page marker.
- `DeviceCard` / `DeviceTable`: online, inspecting, offline, maintenance; actions include opening detail, toggling maintenance, and reconnecting a mock device.
- `AdminVerdict`: approval/rejection choices and memo share one card. Changing a saved verdict requires a memo; the list and save actions share one aligned row. The inspection check card and verdict card stretch to equal height on desktop.

## 6. Content and state model

- Telemetry stages: `MOUNTED`, `STABILIZING`, `BLUR_CHECK`, `OCR`, `LED_CHECK`, `AI_INFERENCE`, `COMPLETED`, `REPOSITION`, `ERROR`, `MANUAL_RETURN`.
- Primary results: `PASS`, `FAIL`, `REPOSITION`, `ERROR`.
- A `FAIL` result retains its originating inspection check. `fail_led` highlights only `PWR LED 점등`; exterior failure highlights only `외관 검사`. Non-failing checks remain visually neutral so the problem location is unambiguous.
- The completed-return screen uses one centered vertical stack for artwork, title, supporting copy, inspection ID, and timeout copy. Its alignment must not depend on static-position behavior of absolutely positioned children.
- Admin authentication explicitly distinguishes signed-out, invalid credentials, expired session, and forbidden role.
- `VITE_APP_MODE=admin` uses JWT login, protected inspection listing/detail/image endpoints, pending queue, verdict confirmation, and retroactive rejection. Combined mode retains the Mock flow. The browser never calls Edge-only `POST /api/v1/inspections`.
- The kiosk subscribes to `inspection/{device_id}/telemetry` only through `VITE_MQTT_BROKER_URL` (MQTT over WebSocket). The repository's `mock/mock_edge.py` publishes standard MQTT on port 1883, so local browsers require a broker that exposes both MQTT 1883 and WebSocket 9001. Manual Figma-state controls remain available when the broker is absent.

## 7. Accessibility constraints

- Korean labels remain visible and are not icon-only where Figma includes text.
- Forms use associated labels; errors use `role="alert"`; progress uses `role="progressbar"`; dialogs use `aria-modal`.
- Status is never communicated by color alone: every badge and check includes text or a symbol.
- Text/background contrast targets WCAG AA. Keyboard users can complete login, filtering, detail review, and confirmation.
- Touch targets and spacing support motor-impaired kiosk users; no time-critical action is required.

## 8. Assets, evidence, and accepted debt

- The board photo and the completion/manual-return character images are downloaded Figma assets and must remain local under `src/assets/figma/`.
- Figma screenshots are reference evidence only under `.artifacts/figma-reference/`; they must never be rendered as product UI.
- Accepted temporary debt: Noto Sans KR is loaded from Google Fonts unless the deployment image later supplies a local font package.
- Accepted temporary debt: the live inspection list currently loads only the newest 100 records. Finalized rejection-to-approval depends on server acceptance of the documented `confirm` endpoint and has no disposable production record for a mutation test.
- Accepted temporary debt: device management is also Mock-backed because no device-management API is defined. Every mutation is session-local and labeled Mock in the UI.
- No real authentication success or backend persistence is claimed by the Mock flow.
- Styling is authored with Tailwind CSS v4 utilities. The only stylesheet is `src/index.css`, which imports Tailwind, declares the dark variant/theme tokens, and contains global accessibility/reset rules.
