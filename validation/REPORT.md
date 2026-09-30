# Validation report

Eyewall's bathtub model is a screening-level screening tool. No observed-event reference flood masks are present in this repository, so agreement metrics are not available. No accuracy claim can be made.

The requested Sentinel-1 proxy for Fani and Amphan has not been exported. Google Earth Engine credentials and an export workflow are not configured. The reference images in docs/ are illustrative images, not georeferenced flood masks suitable for pixel comparisons.

| Event | SAR proxy mask | POD / recall | FAR | CSI | Area ratio | 1-pixel buffer |
|---|---|---:|---:|---:|---:|---:|
| Fani (2019) | unavailable | not computed | not computed | not computed | not computed | not computed |
| Amphan (2020) | unavailable | not computed | not computed | not computed | not computed | not computed |

When reference masks are available, these metrics must be described as agreement between two imperfect estimates, not accuracy against truth. SAR can miss inundation beneath dense vegetation or in built-up areas; the connected bathtub scenario can overestimate flooding across lowlands.
