/** Coordinates are ordered around each ring; repeating the first point is optional.
 * Supply simple, non-self-intersecting rings, with holes inside their outer ring.
 */
export interface MapRegion {
  id: string
  name: string
  polygons: {
    outer: google.maps.LatLngLiteral[]
    holes?: google.maps.LatLngLiteral[][]
  }[]
}

/** Basic validation before sending caller-provided geometry to Google Maps. */
export function validateRegion(region: MapRegion): void {
  if (!region.id || !region.name || !region.polygons?.length) {
    throw new Error('Region needs an id, name and at least one polygon.')
  }
  for (const polygon of region.polygons) {
    for (const ring of [polygon.outer, ...(polygon.holes ?? [])]) {
      if (!Array.isArray(ring) || new Set(ring.map(p => `${p.lat},${p.lng}`)).size < 3) {
        throw new Error('Each region boundary needs at least three distinct coordinates.')
      }
      for (const point of ring) {
        if (!Number.isFinite(point.lat) || !Number.isFinite(point.lng)
          || Math.abs(point.lat) > 90 || Math.abs(point.lng) > 180) {
          throw new Error('Region coordinates must be finite latitude/longitude values.')
        }
      }
    }
  }
}

/** Smallest longitude span, including regions crossing the antimeridian.
 * Bounds are a rectangle; they do not exclude holes or gaps between islands.
 */
export function getRegionBounds(region: MapRegion): google.maps.LatLngBoundsLiteral {
  validateRegion(region)
  const points = region.polygons.flatMap(p => p.outer)
  const lngs = [...new Set(points.map(p => ((p.lng + 180) % 360 + 360) % 360 - 180))].sort((a, b) => a - b)
  let gap = -1
  let west = lngs[0]
  let east = lngs[lngs.length - 1]
  for (let i = 0; i < lngs.length; i++) {
    const next = lngs[(i + 1) % lngs.length] + (i === lngs.length - 1 ? 360 : 0)
    if (next - lngs[i] > gap) {
      gap = next - lngs[i]
      west = lngs[(i + 1) % lngs.length]
      east = lngs[i]
    }
  }
  let north = -90
  let south = 90
  for (const point of points) { north = Math.max(north, point.lat); south = Math.min(south, point.lat) }
  if (north === south || west === east) throw new Error('Region bounds must have non-zero area.')
  return { north, south, west, east }
}
