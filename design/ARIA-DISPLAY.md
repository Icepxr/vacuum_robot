# ARIA · approved outer-ring display

27 September 2026 — presentation-only changes to the GC9A01 renderer in `src/robot/tft.cpp` (`env:robot`). The rectangular OLED and experimental `system_main` renderer are unchanged.

## Visual direction

The accepted design from `aria-co2-ring-concept.html` now drives the firmware renderer. The eCO2 ring occupies the outermost edge with a bottom opening and rounded ends. There is no ARIA wordmark, face, sparkle, boxed card or Manual/Mission text. Four small status icons sit above the primary value; secondary metrics sit below it. The browser concept remains a separate design study, not a live robot page.

Normal screens use the existing 400–2000 ppm scale and band boundaries with the approved softer colors. The central value and eCO2 unit, TVOC, temperature and humidity match the concept; AQI remains in telemetry but is not a separate text row. NOAIR suppresses the gas value. A missing field does not erase other valid fields. Camera failures appear in the crossed camera icon; low storage and missing sensor warnings replace the TVOC row with short warning copy.

Event and connection screens use the same perimeter, one central symbol/value, and a short label with at most one hint. Their perimeter is a uniform state frame, NOT fabricated capture/OCR/mission progress. Success is mint, attention is amber and failure is pink/red. Waiting screens are muted. Native RGB565 drawing uses a flat background and the existing supported fonts; it does not reproduce the concept's browser radial gradient or font exactly.

Emergency stop is intentionally distinct: continuous red perimeter, red background, a stop symbol, E-STOP and Motors off. Its HUD is omitted to keep safety primary. Offline and stale telemetry never claim readiness or show old air readings. No flashing, faces, random animation or automatic page carousel is used.

## Icon truthfulness

- Link: actual local Pi heartbeat; stale display data shows an attention color even if heartbeat remains alive.
- Camera: modern fresh frames with NOCAM/CAPFAIL show failure; an empty warning or later-priority DISK/NOAIR confirms the existing camera-fallback check ran. HOT/NOIP, unknown warnings, stale data and legacy frames leave camera health unknown/gray. The frame carries only one priority warning, not independent health for every subsystem.
- Network: fresh Pi IP availability, not a claim about Wi-Fi radio or internet connectivity. NOIP overrides a retained IP.
- Mode: local joystick, route or pause symbol. Idle is dim; deadman is amber. Mission wins over manual, and safety pause wins over both. No mode text is rendered.

## States and priority

The preview has 21 representative scenes:

- Together: ready, manual driving, mission, waiting for air data, elevated eCO2.
- Connection: awaiting first link, browser connection address, stale telemetry with link alive, Pi disconnected after receiving data.
- Camera: capturing, photo saved / OCR pending, successful reading, unreadable digits, capture failure.
- Attention: drive timeout, no IP, hot Pi, camera missing, storage nearly full, air sensor missing, emergency stop.

Existing priority remains E-stop > Pi offline > fresh event > severe warning (NOIP/HOT). A local manual deadman flag now has explicit presentation after severe warnings, before stale-data/welcome pages. Browser count, local mission/manual flags, gas sentinels and minor warnings determine the remaining screens. Unknown events/warnings retain fitted fallback copy.

All states use existing callbacks and $D fields. No battery, charging, sensor warm-up, actual wheel movement or cleaning progress is inferred. Manual mode does not prove that wheels are moving. Event holding time remains owned by the Pi. No actuator, pin, interlock, command, protocol or display cadence changes were made.

## Preview and validation

Open `aria-round-display-preview.html`; category buttons filter its 21 scenes. These are generated from actual C++ drawing functions with a host-only recording double. All values are examples, not live readings. RGB565 colors come from the firmware; font metrics are approximations, not a pixel-perfect LovyanGFX emulator. Check glyph bounds, readability and colors on the physical screen before deployment.

Run from the repository root with an existing host compiler:

```powershell
g++ -std=c++17 -Wall -Wextra -Werror -I tests/display tests/display/test_round_display.cpp -o .pio/aria-display-test.exe
./.pio/aria-display-test.exe
./.pio/aria-display-test.exe --preview | Out-File -Encoding utf8 design/aria-round-display-preview.html
```

144 host checks cover the scenes, approximate circular text bounds, text budgets (five drawn strings on air pages; three on other pages), outer-edge frame geometry, removal of wordmark/mode text, page priority, stale telemetry, independent sentinels, conservative icon health, legacy frames, deadman, long meter readings, unknown event/warning fallbacks and 200ms cadence. They also verify that missing/baseline gas data does not fabricate fill, high values fill more, capture frames are uniform and emergency frames are continuous. Browser verification checks rendering and category filtering.

The tests do not validate physical I/O, actual LovyanGFX glyph metrics, memory use or the full ESP32 build. Keep fake headers isolated in `tests/display`; never add their include path to PlatformIO.

The full target build command is `pio run -e robot` (no upload). It was tried again for this accepted-design implementation and remains blocked by Windows Application Control for `pio.exe`. Security settings were not altered or bypassed. This display refresh has not been flashed or deployed; its commit and remote publication status are recorded in Git.
