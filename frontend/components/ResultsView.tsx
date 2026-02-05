import React from "react";

interface ResultsViewProps {
  results: {
    restaurants?: any[];
    travel_spots?: any[];
    hotels?: any[];
    car_rentals?: any[];
    flights?: any[];
  };
}

export default function ResultsView({ results }: ResultsViewProps) {
  const {
    restaurants = [],
    travel_spots = [],
    hotels = [],
    car_rentals = [],
    flights = [],
  } = results;

  return (
    <div style={{ display: "grid", gap: 60 }}>
      {/* Restaurants */}
      {restaurants.length > 0 && (
        <section>
          <h2 style={sectionHeaderStyle}>🍽️ Restaurants</h2>
          <p style={sectionSubtitle}>Best dining for your first day</p>
          <div style={{ display: "grid", gap: 20, marginTop: 24 }}>
            {restaurants.map((r) => (
              <RestaurantCard key={r.id} restaurant={r} />
            ))}
          </div>
        </section>
      )}

      {/* Travel Spots */}
      {travel_spots.length > 0 && (
        <section>
          <h2 style={sectionHeaderStyle}>🏛️ Must-See Spots</h2>
          <p style={sectionSubtitle}>Top 3 attractions to visit</p>
          <div style={{ display: "grid", gap: 20, marginTop: 24 }}>
            {travel_spots.map((t) => (
              <AttractionCard key={t.id} attraction={t} />
            ))}
          </div>
        </section>
      )}

      {/* Hotels */}
      {hotels.length > 0 && (
        <section>
          <h2 style={sectionHeaderStyle}>🏨 Hotels</h2>
          <p style={sectionSubtitle}>Recommended accommodations</p>
          <div style={{ display: "grid", gap: 20, marginTop: 24 }}>
            {hotels.map((h) => (
              <HotelCard key={h.id} hotel={h} />
            ))}
          </div>
        </section>
      )}

      {/* Transport */}
      {(car_rentals.length > 0 || flights.length > 0) && (
        <section>
          <h2 style={sectionHeaderStyle}>🚗 Transportation</h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: 40,
              marginTop: 24,
            }}
          >
            {car_rentals.length > 0 && (
              <div>
                <h3 style={subsectionHeaderStyle}>Car Rentals</h3>
                <div style={{ display: "grid", gap: 16, marginTop: 16 }}>
                  {car_rentals.map((c) => (
                    <CarRentalCard key={c.id} car={c} />
                  ))}
                </div>
              </div>
            )}

            {flights.length > 0 && (
              <div>
                <h3 style={subsectionHeaderStyle}>Flights</h3>
                <div style={{ display: "grid", gap: 16, marginTop: 16 }}>
                  {flights.map((f) => (
                    <FlightCard key={f.id} flight={f} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function RestaurantCard({ restaurant }: { restaurant: any }) {
  return (
    <div style={cardStyle}>
      <div style={{ marginBottom: 12 }}>
        <h3 style={cardTitleStyle}>{restaurant.name}</h3>
        <div style={{ display: "flex", gap: 12, marginTop: 6 }}>
          <span style={tagStyle}>{restaurant.cuisine}</span>
          {restaurant.price_range && (
            <span style={tagStyle}>{restaurant.price_range}</span>
          )}
          {restaurant.area && <span style={areaStyle}>{restaurant.area}</span>}
        </div>
      </div>

      <p style={descriptionStyle}>{restaurant.why_recommended}</p>

      {restaurant.tags && restaurant.tags.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {restaurant.tags.map((tag: string) => (
            <span key={tag} style={minTagStyle}>
              {tag}
            </span>
          ))}
        </div>
      )}

      {(restaurant.hours_text || restaurant.phone || restaurant.address) && (
        <div style={enrichedSectionStyle}>
          {restaurant.hours_text && <p>⏰ {restaurant.hours_text}</p>}
          {restaurant.phone && <p>📞 {restaurant.phone}</p>}
          {restaurant.address && <p>📍 {restaurant.address}</p>}
        </div>
      )}

      <a href={restaurant.url} target="_blank" rel="noopener noreferrer" style={linkStyle}>
        View Details →
      </a>
    </div>
  );
}

function AttractionCard({ attraction }: { attraction: any }) {
  return (
    <div style={cardStyle}>
      <div style={{ marginBottom: 12 }}>
        <h3 style={cardTitleStyle}>{attraction.name}</h3>
        <div style={{ display: "flex", gap: 12, marginTop: 6 }}>
          <span style={tagStyle}>{attraction.kind}</span>
          {attraction.area && <span style={areaStyle}>{attraction.area}</span>}
        </div>
      </div>

      <p style={descriptionStyle}>{attraction.why_recommended}</p>

      {attraction.estimated_duration_min && (
        <p style={metaStyle}>
          ⏱️ Estimated visit: {attraction.estimated_duration_min} minutes
        </p>
      )}

      {(attraction.hours_text || attraction.address || attraction.price_hint) && (
        <div style={enrichedSectionStyle}>
          {attraction.hours_text && <p>⏰ {attraction.hours_text}</p>}
          {attraction.price_hint && <p>💰 {attraction.price_hint}</p>}
          {attraction.address && <p>📍 {attraction.address}</p>}
        </div>
      )}

      <a href={attraction.url} target="_blank" rel="noopener noreferrer" style={linkStyle}>
        View Details →
      </a>
    </div>
  );
}

function HotelCard({ hotel }: { hotel: any }) {
  return (
    <div style={cardStyle}>
      <div style={{ marginBottom: 12 }}>
        <h3 style={cardTitleStyle}>{hotel.name}</h3>
        <div style={{ display: "flex", gap: 12, marginTop: 6 }}>
          {hotel.price_per_night && (
            <span style={priceStyle}>{hotel.price_per_night}/night</span>
          )}
          {hotel.area && <span style={areaStyle}>{hotel.area}</span>}
        </div>
      </div>

      <p style={descriptionStyle}>{hotel.why_recommended}</p>

      {hotel.amenities && hotel.amenities.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {hotel.amenities.map((amenity: string) => (
            <span key={amenity} style={minTagStyle}>
              {amenity}
            </span>
          ))}
        </div>
      )}

      {(hotel.hours_text || hotel.phone || hotel.address) && (
        <div style={enrichedSectionStyle}>
          {hotel.hours_text && <p>⏰ {hotel.hours_text}</p>}
          {hotel.phone && <p>📞 {hotel.phone}</p>}
          {hotel.address && <p>📍 {hotel.address}</p>}
        </div>
      )}

      <a href={hotel.url} target="_blank" rel="noopener noreferrer" style={linkStyle}>
        View Details →
      </a>
    </div>
  );
}

function CarRentalCard({ car }: { car: any }) {
  return (
    <div style={compactCardStyle}>
      <h4 style={compactCardTitleStyle}>{car.provider}</h4>
      <p style={compactMetaStyle}>{car.vehicle_class}</p>
      {car.price_per_day && (
        <p style={compactPriceStyle}>{car.price_per_day}/day</p>
      )}
      {car.pickup_location && (
        <p style={compactMetaStyle}>📍 {car.pickup_location}</p>
      )}
      <a href={car.url} target="_blank" rel="noopener noreferrer" style={compactLinkStyle}>
        View Details →
      </a>
    </div>
  );
}

function FlightCard({ flight }: { flight: any }) {
  return (
    <div style={compactCardStyle}>
      <h4 style={compactCardTitleStyle}>{flight.route}</h4>
      {flight.airline && (
        <p style={compactMetaStyle}>✈️ {flight.airline}</p>
      )}
      <p style={compactMetaStyle}>
        {flight.trip_type === "round-trip" ? "Round-trip" : "One-way"}
      </p>
      {flight.price_range && (
        <p style={compactPriceStyle}>{flight.price_range}</p>
      )}
      <a href={flight.url} target="_blank" rel="noopener noreferrer" style={compactLinkStyle}>
        View Details →
      </a>
    </div>
  );
}

// Styles
const sectionHeaderStyle: React.CSSProperties = {
  fontSize: 32,
  fontWeight: 700,
  color: "#1d1d1f",
  margin: 0,
  letterSpacing: "-0.02em",
};

const sectionSubtitle: React.CSSProperties = {
  fontSize: 17,
  color: "#86868b",
  marginTop: 8,
};

const subsectionHeaderStyle: React.CSSProperties = {
  fontSize: 24,
  fontWeight: 600,
  color: "#1d1d1f",
  margin: 0,
};

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  borderRadius: 16,
  padding: 24,
  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.08)",
  border: "1px solid #e8e8ed",
  transition: "transform 0.2s, box-shadow 0.2s",
};

const cardTitleStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 600,
  color: "#1d1d1f",
  margin: 0,
};

const descriptionStyle: React.CSSProperties = {
  fontSize: 15,
  color: "#6e6e73",
  lineHeight: 1.6,
  margin: "12px 0 0 0",
};

const tagStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "6px 12px",
  fontSize: 13,
  fontWeight: 600,
  color: "#0071e3",
  background: "#e8f4ff",
  borderRadius: 8,
};

const areaStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "6px 12px",
  fontSize: 13,
  color: "#6e6e73",
  background: "#f5f5f7",
  borderRadius: 8,
};

const priceStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "6px 12px",
  fontSize: 14,
  fontWeight: 600,
  color: "#1d8b3a",
  background: "#e8f5e9",
  borderRadius: 8,
};

const minTagStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "4px 10px",
  fontSize: 12,
  color: "#6e6e73",
  background: "#f5f5f7",
  borderRadius: 6,
};

const metaStyle: React.CSSProperties = {
  fontSize: 14,
  color: "#86868b",
  margin: "8px 0 0 0",
};

const enrichedSectionStyle: React.CSSProperties = {
  marginTop: 16,
  paddingTop: 16,
  borderTop: "1px solid #e8e8ed",
  fontSize: 14,
  color: "#6e6e73",
  lineHeight: 1.8,
};

const linkStyle: React.CSSProperties = {
  display: "inline-block",
  marginTop: 16,
  fontSize: 15,
  fontWeight: 600,
  color: "#0071e3",
  textDecoration: "none",
  transition: "opacity 0.2s",
};

const compactCardStyle: React.CSSProperties = {
  background: "#ffffff",
  borderRadius: 12,
  padding: 20,
  boxShadow: "0 2px 6px rgba(0, 0, 0, 0.06)",
  border: "1px solid #e8e8ed",
};

const compactCardTitleStyle: React.CSSProperties = {
  fontSize: 18,
  fontWeight: 600,
  color: "#1d1d1f",
  margin: 0,
};

const compactMetaStyle: React.CSSProperties = {
  fontSize: 14,
  color: "#6e6e73",
  margin: "6px 0 0 0",
};

const compactPriceStyle: React.CSSProperties = {
  fontSize: 16,
  fontWeight: 600,
  color: "#1d8b3a",
  margin: "8px 0 0 0",
};

const compactLinkStyle: React.CSSProperties = {
  display: "inline-block",
  marginTop: 12,
  fontSize: 14,
  fontWeight: 600,
  color: "#0071e3",
  textDecoration: "none",
};
