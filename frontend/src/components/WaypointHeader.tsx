interface WaypointHeaderProps {
  routeLabel: string;
}

export function WaypointHeader({ routeLabel }: WaypointHeaderProps) {
  return (
    <header className="waypoint-header">
      <div className="waypoint-header__mark">
        <span aria-hidden="true">WP</span>
        <span>Voice lab</span>
      </div>

      <div className="waypoint-header__route">
        <span className="waypoint-header__route-line" aria-hidden="true" />
        <span>{routeLabel}</span>
      </div>
    </header>
  );
}

