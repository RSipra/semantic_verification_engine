
## Objective: To modify or rebuild the Phase 1 VM without pushing Phase 2 code into it.

1. Isolate Phase 2 Code: Ensure all Phase 2 files are moved out of the sync path or the local folder is renamed (e.g., project-v2-refactor).

2. Restore Phase 1 Files: Ensure the local folder harry-potter-trivia contains only the Phase 1 code (Python script, Dockerfile, dataset).

3. Establish Tunnel: Turn on Tailscale.

4. Open Portal: Launch VS Code and connect to ssh trivia.

5. Manual Verification: Once connected, check the VS Code sidebar. If you see FastAPI files, Stop Immediately and disconnect.

6. Execute Task: Perform the rebuild or fix.

7. Close & Clean: Close the Remote Connection before returning to Phase 2 development.