# Coaching refactor validation — October 11, 2026

- Backend: 47 tests passed, including all existing scoring, rally, video and session tests. One existing Starlette/httpx deprecation warning remains.
- Frontend: `npm run build` passed TypeScript checking and Vite production bundling.
- Real inference: the existing badminton starter video completed with 527 processed frames, version 2 analytics and no processing error. The sample had no court corners and no completed rally decision, so physical movement measurements and completed-rally averages correctly remained unavailable. This confirms pipeline integration, not match-level accuracy.
- Browser: verified Overview, Sessions, Tactical Report and the New Session modal, including Deep Analysis helper text. No browser warnings or errors were recorded. Hardware labels, benchmark cards, pixel speed and compute-savings cards are removed.
- Saved browser preview: `coaching-report.png`. It shows the uncalibrated sample's honest missing-data state.

Unit tests validate populated measurements using known court coordinates and rally events. Accuracy on arbitrary match footage, automatic technique grading and true airborne shot-speed reconstruction have not been established.
