/** Attach Google's COUNTRY layer styling without fetching places or boundary coordinates. */
export function highlightCountry(
  map: google.maps.Map,
  placeId: string,
  onStatus: (message: string) => void,
): () => void {
  let layer: google.maps.FeatureLayer | undefined
  const outline: google.maps.FeatureStyleOptions = {
    strokeColor: '#4f46e5', strokeOpacity: 1, strokeWeight: 3,
    // Outline only; keep map clicks available for placing guesses.
    fillOpacity: 0,
  }
  const style: google.maps.FeatureStyleFunction = ({ feature }) =>
    (feature as google.maps.PlaceFeature).placeId === placeId ? outline : null

  const update = () => {
    // Capabilities may arrive after map construction, or change on renderer fallback.
    if (!map.getMapCapabilities().isDataDrivenStylingAvailable) {
      onStatus('Country highlighting unavailable. Check the vector Map ID and its Country layer.')
      return
    }
    layer = map.getFeatureLayer(google.maps.FeatureType.COUNTRY)
    if (!layer.isAvailable) {
      onStatus('Country highlighting unavailable. Enable the Country layer for this Map ID.')
      return
    }
    layer.style = style
    onStatus('')
  }
  const listener = map.addListener('mapcapabilities_changed', update)
  update()
  return () => {
    listener.remove()
    if (layer?.isAvailable) layer.style = null
  }
}
