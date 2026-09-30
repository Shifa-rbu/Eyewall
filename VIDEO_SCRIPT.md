# Eyewall walkthrough video (3–5 minutes)

| Time | Shot |
|---|---|
| 0:00–0:40 | Odisha coast map; introduce the 24-hour preparation window |
| 0:40–1:25 | Scenario controls and screening exposure layer |
| 1:25–2:15 | Road accessibility and total-water-level components |
| 2:15–2:55 | CAP 1.2 exercise alert |
| 2:55–3:45 | Human review queue and audit record |

## Spoken script

**[Coastal Odisha map]** In the 24 hours before a cyclone makes landfall, district teams need to see which communities and routes may become difficult to reach. In the Kendrapara–Paradip delta, that can include people who depend on a single road, a nearby shelter, or a facility with limited backup access. Eyewall brings several screening views together so a person can examine the scenario and decide what needs checking on the ground.

**[Show the map and move the surge control]** This map combines local elevation, mapped assets, and historical cyclone tracks. The blue overlay is a sea-connected bathtub screening scenario. It shows land that could be connected to the sea below the selected scenario level. It is not a hydrodynamic forecast, and the mapped facilities and roads may be incomplete. The exposure counts describe mapped assets in the scenario; they are not population figures.

**[Open exposure and road views]** The console reports screened exposure for medical, shelter, and power assets, along with road and grid lengths intersecting the scenario. Road accessibility adds a network view: it screens for impassable road segments, chokepoints, and communities that may become isolated. These are decision-support estimates. Teams should verify critical routes and facilities with local responders.

**[Show total water level components]** The water-level view breaks the scenario into surge, tide, pressure, wind, and wave contributions. The components help explain what is being considered; they do not turn this screening tool into a coastal hydrodynamic forecast. For operational conditions, use official IMD and OSDMA information.

**[Show the alert preview]** Eyewall can prepare a CAP 1.2 exercise alert for review. Its status is pinned to **Exercise**, so this is a demonstration message, not an official warning. A configured server may use Gemini Flash to draft text; a number guardrail checks the draft, and a local template is used when the model path is unavailable or rejected.

**[Show the review queue and audit export]** A draft waits for a person to review it. The reviewer can approve, reject, or edit it, and the decision is recorded in a hash-chained audit trail. There is no automatic dispatch. The system does not retrieve Earth Engine or Sentinel-1 imagery, and it does not provide population figures. People remain responsible for checking the evidence, consulting official guidance, and deciding what action to take.
