# STEP Level 2 Feature Recognition — Optional Dependency

## Status: OPTIONAL_DEPENDENCY_MISSING (standard deployment)

STEP Level 2 B-Rep feature recognition requires:
- pythonocc-core >= 7.7.0 (Open CASCADE Technology Python bindings)
- Install: pip install pythonocc-core

Without this dependency:
- STEP upload proceeds (Level 0/1: header parsing, entity inventory)
- Feature recognition returns recognition_level: "LEVEL_1_ENTITY_COUNT"
- No machining features extracted from STEP geometry
- DXF 2D recognition always available without pythonocc-core

## Demo Recommendation
Use DXF 2D fixtures for demos on standard deployments.
The hydraulic spool demo part (MP-DEMO-001) works fully via manual req_set input
and does not require STEP file upload.
