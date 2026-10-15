import { Component, type ReactNode } from 'react';
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface Props {
  latitude: number | null;
  longitude: number | null;
  onPick: (latitude: number, longitude: number) => void;
}

function ClickHandler({ onPick }: { onPick: Props['onPick'] }) {
  useMapEvents({
    click(e) {
      onPick(Number(e.latlng.lat.toFixed(4)), Number(e.latlng.lng.toFixed(4)));
    },
  });
  return null;
}

function Recenter({ center }: { center: [number, number] }) {
  const map = useMap();
  map.setView(center, map.getZoom());
  return null;
}

const FALLBACK: [number, number] = [20, 85];

export function isValidPoint(lat: number | null, lon: number | null): boolean {
  return (
    typeof lat === 'number' &&
    typeof lon === 'number' &&
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= -90 &&
    lat <= 90 &&
    lon >= -180 &&
    lon <= 180
  );
}

function MapView({ latitude, longitude, onPick }: Props) {
  const point: [number, number] | null =
    typeof latitude === 'number' &&
    typeof longitude === 'number' &&
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
      ? [latitude, longitude]
      : null;
  const center: [number, number] = point ?? FALLBACK;
  return (
    <div className="map-wrap">
      <MapContainer
        center={center}
        zoom={5}
        scrollWheelZoom={false}
        style={{ height: 260, width: '100%' }}
        aria-label="Region selection map. Click to set coordinates."
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Recenter center={center} />
        <ClickHandler onPick={onPick} />
        {point && (
          <CircleMarker center={point} radius={8} pathOptions={{ color: '#c2410c' }} />
        )}
      </MapContainer>
      <p className="hint">
        Click the map to set the point coordinates. Map tiles © OpenStreetMap
        contributors.
      </p>
    </div>
  );
}

class MapErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <p className="hint" data-testid="map-fallback">
          Interactive map unavailable here — please enter latitude/longitude manually.
        </p>
      );
    }
    return this.props.children;
  }
}

export default function MapPicker(props: Props) {
  return (
    <MapErrorBoundary>
      <MapView {...props} />
    </MapErrorBoundary>
  );
}
