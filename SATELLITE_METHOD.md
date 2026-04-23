# Satellite Method

## Goal
Estimate a **visible lithium-site footprint** around Cauchari-Olaroz using satellite imagery, without machine learning.

## What this method does
- loads Sentinel-2 imagery in Google Earth Engine
- compares **late 2023** with **late 2024**
- applies a simple rule-based mask to detect likely evaporation ponds / brine-like visible surfaces
- calculates an estimated visible footprint area in `km²`

## Why this is good for the jury
- simple
- explainable
- visual
- directly connected to the trade story

## What it does **not** claim
- not exact production
- not exact truck counts
- not proof of fraud

## What it gives you
- a before/after satellite visual
- an estimated site-footprint area
- a simple statement:

`Trade data tells us where to look. Satellite footprint tells us whether the site looks consistent with real industrial activity.`

## Files
- [gee_cauchari_surface_estimation.js](C:/Users/liad/Documents/hackaton/gee_cauchari_surface_estimation.js)

## Suggested narration
`Here, we do not try to infer exact production from space. We estimate whether the visible industrial footprint around a known lithium site expands in a way that is consistent with the trade story.`
