// OriginTrace - Cauchari-Olaroz visible footprint estimation
//
// Goal:
// Estimate the visible evaporation-pond / lithium-site footprint over time
// using a simple, explainable, non-ML satellite rule set in Google Earth Engine.
//
// Why this works for the demo:
// - We are not claiming exact production from satellite
// - We are estimating visible industrial footprint around a known lithium site
// - We compare that footprint through time to test whether industrial growth is plausible
//
// Data:
// - Sentinel-2 Surface Reflectance Harmonized
// - Two time windows: late 2023 vs late 2024
//
// Main output:
// - Map layers for each period
// - Detected pond/footprint masks
// - Estimated area in km²
// - A simple comparison chart


// ------------------------------------------------------------
// 1. Site geometry
// ------------------------------------------------------------
// Approximate center of Cauchari-Olaroz / Minera Exar operation
// Source reference used for project location:
// https://www.lithium-argentina.com/projects/cauchari-olaroz
var sitePoint = ee.Geometry.Point([-66.647, -23.427]);

// Wider context for display
var roi = sitePoint.buffer(14000).bounds();

// Focus area for area calculation
var analysisRoi = sitePoint.buffer(7000).bounds();

Map.centerObject(sitePoint, 12);


// ------------------------------------------------------------
// 2. Helper functions
// ------------------------------------------------------------
function maskS2Clouds(image) {
  var qa = image.select('QA60');
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;

  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
    .and(qa.bitwiseAnd(cirrusBitMask).eq(0));

  return image
    .updateMask(mask)
    .divide(10000)
    .copyProperties(image, ['system:time_start']);
}

function buildComposite(startDate, endDate) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(roi)
    .filterDate(startDate, endDate)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    .map(maskS2Clouds)
    .median()
    .clip(roi);
}

function addIndices(image) {
  var ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI');
  var greenRed = image.select('B3').divide(image.select('B4')).rename('GREEN_RED');
  var blueRed = image.select('B2').divide(image.select('B4')).rename('BLUE_RED');
  return image.addBands([ndvi, ndwi, greenRed, blueRed]);
}

// Simple explainable rule:
// We are looking for visible evaporation ponds / brine-like surfaces around the site.
// Heuristic logic:
// - almost no vegetation
// - some water/brine-like behavior in green vs NIR
// - green/cyan tone stronger than red
// - avoid tiny noisy patches
function detectVisibleFootprint(imageWithIndices) {
  var mask = imageWithIndices.select('NDVI').lt(0.10)
    .and(imageWithIndices.select('NDWI').gt(-0.05))
    .and(imageWithIndices.select('GREEN_RED').gt(1.12))
    .and(imageWithIndices.select('BLUE_RED').gt(0.95))
    .and(imageWithIndices.select('B8').lt(0.22))
    .selfMask();

  // Remove tiny noisy detections
  var cleaned = mask
    .connectedPixelCount(100, true)
    .gte(8)
    .selfMask();

  return cleaned.rename('visible_footprint');
}

function computeAreaKm2(maskImage, geometry) {
  var areaImage = ee.Image.pixelArea().updateMask(maskImage);
  var area = areaImage.reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: geometry,
    scale: 10,
    maxPixels: 1e10
  }).get('area');

  return ee.Number(area).divide(1e6);
}


// ------------------------------------------------------------
// 3. Time windows
// ------------------------------------------------------------
// Use comparable windows near year-end to keep the story simple for the jury.
var periodAStart = '2023-10-01';
var periodAEnd = '2024-01-31';

var periodBStart = '2024-08-01';
var periodBEnd = '2024-12-31';


// ------------------------------------------------------------
// 4. Build composites and detection masks
// ------------------------------------------------------------
var compositeA = addIndices(buildComposite(periodAStart, periodAEnd));
var compositeB = addIndices(buildComposite(periodBStart, periodBEnd));

var footprintA = detectVisibleFootprint(compositeA).clip(analysisRoi);
var footprintB = detectVisibleFootprint(compositeB).clip(analysisRoi);

var areaA = computeAreaKm2(footprintA, analysisRoi);
var areaB = computeAreaKm2(footprintB, analysisRoi);
var areaDelta = areaB.subtract(areaA);
var pctDelta = areaDelta.divide(areaA.max(0.0001)).multiply(100);


// ------------------------------------------------------------
// 5. Visual layers
// ------------------------------------------------------------
var trueColor = {
  bands: ['B4', 'B3', 'B2'],
  min: 0.02,
  max: 0.25,
  gamma: 1.1
};

var footprintVisA = {palette: ['#00f5d4'], opacity: 0.75};
var footprintVisB = {palette: ['#ffb703'], opacity: 0.75};

Map.addLayer(compositeA, trueColor, 'True color | Late 2023');
Map.addLayer(footprintA, footprintVisA, 'Detected visible footprint | Late 2023', false);
Map.addLayer(compositeB, trueColor, 'True color | Late 2024', false);
Map.addLayer(footprintB, footprintVisB, 'Detected visible footprint | Late 2024');
Map.addLayer(analysisRoi, {color: '#ffffff'}, 'Analysis ROI', false);


// ------------------------------------------------------------
// 6. Outputs for the console
// ------------------------------------------------------------
print('Site center', sitePoint);
print('Analysis ROI', analysisRoi);
print('Estimated visible footprint area (km²) | Late 2023', areaA);
print('Estimated visible footprint area (km²) | Late 2024', areaB);
print('Estimated area delta (km²)', areaDelta);
print('Estimated area change (%)', pctDelta);


// ------------------------------------------------------------
// 7. Jury-friendly chart
// ------------------------------------------------------------
var areaFeatureCollection = ee.FeatureCollection([
  ee.Feature(null, {period: 'Late 2023', area_km2: areaA}),
  ee.Feature(null, {period: 'Late 2024', area_km2: areaB})
]);

var areaChart = ui.Chart.feature.byFeature(areaFeatureCollection, 'period', 'area_km2')
  .setChartType('ColumnChart')
  .setOptions({
    title: 'Estimated visible lithium-site footprint',
    legend: {position: 'none'},
    colors: ['#d97732'],
    hAxis: {title: 'Period'},
    vAxis: {title: 'Area (km²)'},
    backgroundColor: '#ffffff'
  });

print(areaChart);


// ------------------------------------------------------------
// 8. Optional exports
// ------------------------------------------------------------
// Export these if you want to plug real before/after frames into demo_site.html.
// After export, download them into the project folder with these exact names:
// - cauchari_late_2023.png
// - cauchari_late_2024.png
// - cauchari_detected_footprint_2024.png

Export.image.toDrive({
  image: compositeA.visualize(trueColor),
  description: 'cauchari_late_2023',
  region: roi,
  scale: 10,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: compositeB.visualize(trueColor),
  description: 'cauchari_late_2024',
  region: roi,
  scale: 10,
  maxPixels: 1e10
});

Export.image.toDrive({
  image: footprintB.visualize(footprintVisB),
  description: 'cauchari_detected_footprint_2024',
  region: analysisRoi,
  scale: 10,
  maxPixels: 1e10
});

Export.table.toDrive({
  collection: areaFeatureCollection,
  description: 'cauchari_visible_footprint_summary',
  fileFormat: 'CSV'
});
