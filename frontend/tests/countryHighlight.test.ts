import assert from 'node:assert/strict'
import test from 'node:test'
import { highlightCountry } from '../src/common/googleMapUtil/countryHighlight.ts'

// Exercise late Google capability availability and listener cleanup without API calls.
globalThis.google = { maps: { FeatureType: { COUNTRY: 'COUNTRY' } } } as typeof google

function mockMap(available = true, countryAvailable = true) {
  const callbacks = new Set<() => void>()
  const layer = { isAvailable: countryAvailable, style: null } as google.maps.FeatureLayer
  let lookups = 0
  const map = {
    getMapCapabilities: () => ({ isDataDrivenStylingAvailable: available }),
    getFeatureLayer: (type: google.maps.FeatureType) => {
      assert.equal(type, 'COUNTRY')
      lookups++
      return layer
    },
    addListener: (name: string, callback: () => void) => {
      assert.equal(name, 'mapcapabilities_changed')
      callbacks.add(callback)
      return { remove: () => callbacks.delete(callback) }
    },
  } as unknown as google.maps.Map
  return {
    map, layer, callbacks,
    get lookups() { return lookups },
    setAvailable(value: boolean) {
      available = value
      callbacks.forEach(callback => callback())
    },
  }
}

function styleFor(layer: google.maps.FeatureLayer, placeId: string) {
  const style = layer.style as google.maps.FeatureStyleFunction
  return style({ feature: { placeId } as google.maps.PlaceFeature })
}

test('only the requested country gets an outline, without a filled overlay', () => {
  const { map, layer } = mockMap()
  const messages: string[] = []
  const detach = highlightCountry(map, 'country-one', message => messages.push(message))
  assert.equal(styleFor(layer, 'country-one')?.strokeOpacity, 1)
  assert.equal(styleFor(layer, 'country-one')?.fillOpacity, 0)
  assert.equal(styleFor(layer, 'country-two'), null)
  assert.equal(messages.at(-1), '')
  detach()
})

test('late capabilities apply the highlight and clear the unavailable message', () => {
  const value = mockMap(false)
  const messages: string[] = []
  const detach = highlightCountry(value.map, 'country-one', message => messages.push(message))
  assert.equal(value.lookups, 0)
  assert.match(messages.at(-1)!, /unavailable/)
  value.setAvailable(true)
  assert.equal(messages.at(-1), '')
  assert.ok(styleFor(value.layer, 'country-one'))
  detach()
})

test('a missing Country layer is reported without trying to style it', () => {
  const { map, layer } = mockMap(true, false)
  const messages: string[] = []
  const detach = highlightCountry(map, 'country-one', message => messages.push(message))
  assert.equal(layer.style, null)
  assert.match(messages.at(-1)!, /Enable the Country layer/)
  detach()
})

test('switching or removing a country clears old styling and subscriptions', () => {
  const value = mockMap()
  const detachFirst = highlightCountry(value.map, 'country-one', () => {})
  detachFirst()
  assert.equal(value.layer.style, null)
  assert.equal(value.callbacks.size, 0)
  const detachSecond = highlightCountry(value.map, 'country-two', () => {})
  assert.equal(styleFor(value.layer, 'country-one'), null)
  assert.ok(styleFor(value.layer, 'country-two'))
  detachSecond()
  value.setAvailable(true)
  assert.equal(value.layer.style, null)
  assert.equal(value.callbacks.size, 0)
})

test('renderer fallback reports unavailability and recovers without a new map', () => {
  const value = mockMap()
  const messages: string[] = []
  const detach = highlightCountry(value.map, 'country-one', message => messages.push(message))
  value.setAvailable(false)
  assert.match(messages.at(-1)!, /unavailable/)
  value.setAvailable(true)
  assert.equal(messages.at(-1), '')
  assert.ok(styleFor(value.layer, 'country-one'))
  detach()
})
