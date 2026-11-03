# Proposed Agent37 workflow - NOT YET RUN

This workflow has not been executed. It is the plan for the hosted run once the
account and credit use are approved.

1. Sign in to the Agent37 account for this project (account authority pending).
2. Create a Free Hermes agent; note the instance ID from the dashboard URL.
3. Upload the StudyPilot source archive to the agent's computer.
4. Ask the agent to extract it, run the test suite, then run the pipeline on the
   synthetic samples with a given days-left value.
5. Ask the agent to open analysis.json and validation_log.md and confirm the
   counts (mapped, unmapped, errors) match the local run.
6. Ask for one variation (different days-left) to show the agent iterating.
7. Capture the instance dashboard screenshot (Sessions overview), not the chat view.
