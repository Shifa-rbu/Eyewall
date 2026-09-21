// Historical Sentinel-1 evidence for Cyclone Fani, not a live feed.
// Kendrapara–Paradip delta: [west, south, east, north].
var roi = ee.Geometry.Rectangle([86.35, 20.05, 86.75, 20.40]);

var collection = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(roi)
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'));

var before = collection
  .filterDate('2019-04-20', '2019-04-28')
  .select('VV')
  .median()
  .clip(roi);

var after = collection
  .filterDate('2019-05-03', '2019-05-10')
  .select('VV')
  .median()
  .clip(roi);

var visualization = {min: -25, max: 0};

Map.centerObject(roi, 10);
Map.addLayer(before, visualization, 'BEFORE');
Map.addLayer(after, visualization, 'AFTER');
