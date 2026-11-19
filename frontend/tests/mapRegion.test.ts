import assert from 'node:assert/strict'
import test from 'node:test'
import { getRegionBounds, validateRegion } from '../src/common/googleMapUtil/MapRegion.ts'
import type { MapRegion } from '../src/common/googleMapUtil/MapRegion.ts'

function region(outer: { lat: number; lng: number }[]): MapRegion {
  return { id: 'test', name: 'Test region', polygons: [{ outer }] }
}

test('ordinary bounds enclose every island; holes do not change bounds', () => {
  const value = region([{ lat: 10, lng: 20 }, { lat: 11, lng: 20 }, { lat: 11, lng: 22 }])
  value.polygons[0].holes = [[{ lat: 10.5, lng: 20.5 }, { lat: 10.6, lng: 20.5 }, { lat: 10.6, lng: 20.6 }]]
  value.polygons.push({ outer: [{ lat: -3, lng: 25 }, { lat: -2, lng: 25 }, { lat: -2, lng: 26 }] })
  assert.deepEqual(getRegionBounds(value), { south: -3, north: 11, west: 20, east: 26 })
})

test('dateline region uses a short crossing rectangle instead of almost the whole world', () => {
  const value = region([{ lat: -20, lng: 179 }, { lat: -16, lng: 179 }, { lat: -16, lng: -178 }])
  assert.deepEqual(getRegionBounds(value), { south: -20, north: -16, west: 179, east: -178 })
})

test('closed rings are accepted, and input coordinates are not mutated', () => {
  const value = region([{ lat: 1, lng: -74 }, { lat: 2, lng: -74 }, { lat: 2, lng: -73 }, { lat: 1, lng: -74 }])
  const before = structuredClone(value)
  assert.deepEqual(getRegionBounds(value), { south: 1, north: 2, west: -74, east: -73 })
  assert.deepEqual(value, before)
})

test('invalid, empty and degenerate regions fail instead of silently restricting to another location', () => {
  assert.throws(() => validateRegion({ id: 'bad', name: 'Bad', polygons: [] }))
  assert.throws(() => validateRegion(region([{ lat: 0, lng: 0 }, { lat: 0, lng: 0 }, { lat: 1, lng: 1 }])))
  for (const point of [{ lat: NaN, lng: 0 }, { lat: 91, lng: 0 }, { lat: 1, lng: Infinity }, { lat: 1, lng: -181 }]) {
    assert.throws(() => validateRegion(region([point, { lat: 2, lng: 2 }, { lat: 3, lng: 3 }])))
  }
  assert.throws(() => getRegionBounds(region([{ lat: 0, lng: 1 }, { lat: 0, lng: 2 }, { lat: 0, lng: 3 }])))
})
