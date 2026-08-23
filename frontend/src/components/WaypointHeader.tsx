interface WaypointHeaderProps {
  routeLabel: string;
}

export function WaypointHeader({ routeLabel }: WaypointHeaderProps) {
  return (
    <header className="waypoint-header">
      <div className="waypoint-header__mark">
        <img
          className="waypoint-header__brand-icon"
          src="/waypoint-mark.svg"
          width={31}
          height={31}
          alt="Waypoint"
        />
        <span>Voice lab</span>
      </div>

      <div className="waypoint-header__route">
        <span className="waypoint-header__route-line" aria-hidden="true" />
        <span>{routeLabel}</span>
      </div>
    </header>
  );
}

