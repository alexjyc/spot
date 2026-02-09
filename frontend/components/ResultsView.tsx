import React from "react";
import {
  Utensils,
  MapPin,
  Building2,
  Car,
  Plane,
  Clock,
  Phone,
  CreditCard,
  ChevronRight,
  Star,
  FileText,
  Table,
} from "lucide-react";
import { getExportUrl } from "../lib/api";
import type { SpotOnResults, Restaurant, TravelSpot, Hotel, CarRental, Flight } from "../types/api";

interface ResultsViewProps {
  results: SpotOnResults;
  runId?: string | null;
}

const TOP_N = 3;
const TOP_N_RESTAURANTS = 4;

export default function ResultsView({ results, runId }: ResultsViewProps) {
  const {
    restaurants = [],
    travel_spots = [],
    hotels = [],
    car_rentals = [],
    flights = [],
  } = results;

  const topRestaurants = restaurants.slice(0, TOP_N_RESTAURANTS);
  const refRestaurants = restaurants.slice(TOP_N_RESTAURANTS);

  const topSpots = travel_spots.slice(0, TOP_N);
  const refSpots = travel_spots.slice(TOP_N);

  const topHotels = hotels.slice(0, TOP_N);
  const refHotels = hotels.slice(TOP_N);

  const topCars = car_rentals.slice(0, TOP_N);
  const refCars = car_rentals.slice(TOP_N);

  const topFlights = flights.slice(0, TOP_N);
  const refFlights = flights.slice(TOP_N);

  return (
    <div style={{ display: "grid", gap: 80, paddingBottom: 60 }}>
      {/* Export Toolbar */}
      {runId && (
        <div style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 12,
          paddingTop: 8,
        }}>
          <a
            href={getExportUrl(runId, "pdf")}
            download
            style={exportButtonStyle}
          >
            <FileText size={16} />
            <span>Export PDF</span>
          </a>
          <a
            href={getExportUrl(runId, "xlsx")}
            download
            style={exportButtonStyle}
          >
            <Table size={16} />
            <span>Export Spreadsheet</span>
          </a>
        </div>
      )}

      {/* Transport */}
      {(car_rentals.length > 0 || flights.length > 0) && (
        <section className="animate-fadeIn">
          <SectionHeader
            icon={<Car size={28} className="text-[#FF4F00]" />}
            title="Transportation"
            subtitle="Getting there and getting around."
          />
          <div style={{ display: "grid", gap: 40, marginTop: 32 }}>
            {car_rentals.length > 0 && (
              <div>
                <h3 style={subHeaderStyle}>Car Rentals</h3>
                <div style={compactGridStyle}>
                  {topCars.map((c, i) => (
                    <CarRentalCard key={c.id || i} car={c} />
                  ))}
                </div>
                {refCars.length > 0 && (
                  <ReferenceSection title="More car rentals">
                    {refCars.map((c, i) => (
                      <RefRow key={c.id || i} name={c.provider} detail={c.vehicle_class} price={c.price_per_day ? `${c.price_per_day}/day` : undefined} url={c.url} />
                    ))}
                  </ReferenceSection>
                )}
              </div>
            )}

            {flights.length > 0 && (
              <div>
                <h3 style={subHeaderStyle}>Flights</h3>
                <div style={compactGridStyle}>
                  {topFlights.map((f, i) => (
                    <FlightCard key={f.id || i} flight={f} />
                  ))}
                </div>
                {refFlights.length > 0 && (
                  <ReferenceSection title="More flights">
                    {refFlights.map((f, i) => (
                      <RefRow key={f.id || i} name={f.airline ? `${f.airline} — ${f.route}` : f.route} detail={f.trip_type === "round-trip" ? "Round-trip" : "One-way"} price={f.price_range || undefined} url={f.url} />
                    ))}
                  </ReferenceSection>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Hotels */}
      {hotels.length > 0 && (
        <section className="animate-fadeIn" style={{ animationDelay: "0.1s" }}>
          <SectionHeader
            icon={<Building2 size={28} className="text-[#FF4F00]" />}
            title="Where to Stay"
            subtitle="Highly rated accommodations for comfort."
          />
          <div style={gridStyle}>
            {topHotels.map((h, i) => (
              <HotelCard key={h.id || i} hotel={h} />
            ))}
          </div>
          {refHotels.length > 0 && (
            <ReferenceSection title="More hotels">
              {refHotels.map((h, i) => (
                <RefRow key={h.id || i} name={h.name} detail={h.why_recommended?.slice(0, 60)} price={h.price_per_night ? `${h.price_per_night}/night` : undefined} url={h.url} />
              ))}
            </ReferenceSection>
          )}
        </section>
      )}

      {/* Restaurants */}
      {restaurants.length > 0 && (
        <section className="animate-fadeIn" style={{ animationDelay: "0.2s" }}>
          <SectionHeader
            icon={<Utensils size={28} className="text-[#FF4F00]" />}
            title="Dining"
            subtitle="Curated culinary experiences for your first meal."
          />
          <div style={gridStyle}>
            {topRestaurants.map((r, i) => (
              <RestaurantCard key={r.id || i} restaurant={r} />
            ))}
          </div>
          {refRestaurants.length > 0 && (
            <ReferenceSection title="More restaurants">
              {refRestaurants.map((r, i) => (
                <RefRow key={r.id || i} name={r.name} detail={[r.cuisine, r.area].filter(Boolean).join(" · ")} price={r.price_range || undefined} url={r.url} />
              ))}
            </ReferenceSection>
          )}
        </section>
      )}

      {/* Travel Spots */}
      {travel_spots.length > 0 && (
        <section className="animate-fadeIn" style={{ animationDelay: "0.3s" }}>
          <SectionHeader
            icon={<MapPin size={28} className="text-[#FF4F00]" />}
            title="Must-See Spots"
            subtitle="Top attractions to start your journey."
          />
          <div style={gridStyle}>
            {topSpots.map((t, i) => (
              <AttractionCard key={t.id || i} attraction={t} />
            ))}
          </div>
          {refSpots.length > 0 && (
            <ReferenceSection title="More attractions">
              {refSpots.map((t, i) => (
                <RefRow key={t.id || i} name={t.name} detail={t.kind} url={t.url} />
              ))}
            </ReferenceSection>
          )}
        </section>
      )}
    </div>
  );
}

// -- Components --

function SectionHeader({ icon, title, subtitle }: { icon: React.ReactNode, title: string, subtitle: string }) {
  return (
    <div style={{ marginBottom: 32, display: "flex", alignItems: "flex-start", gap: 16 }}>
      <div style={{
        padding: 12,
        background: "#fff7ed",
        borderRadius: "16px",
        color: "#FF4F00"
      }}>
        {icon}
      </div>
      <div>
        <h2 style={{
          fontSize: 32,
          fontWeight: 700,
          color: "#1d1d1f",
          letterSpacing: "-0.03em",
          lineHeight: 1.1,
          margin: "4px 0 8px 0"
        }}>
          {title}
        </h2>
        <p style={{ fontSize: 17, color: "#86868b", margin: 0, fontWeight: 400 }}>{subtitle}</p>
      </div>
    </div>
  );
}

function ReferenceSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 24 }}>
      <h4 style={{ fontSize: 14, color: "#86868b", marginBottom: 12, fontWeight: 600 }}>{title}</h4>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {children}
      </div>
    </div>
  );
}

function RefRow({ name, detail, price, url }: { name: string; detail?: string; price?: string; url: string }) {
  return (
    <div style={refRowStyle}>
      <span style={refNameStyle}>{name}</span>
      {detail && <span style={refDetailStyle}>{detail}</span>}
      {price && <span style={refPriceStyle}>{price}</span>}
      <a href={url} target="_blank" rel="noopener noreferrer" style={refLinkStyle}>View</a>
    </div>
  );
}

function RestaurantCard({ restaurant }: { restaurant: Restaurant }) {
  return (
    <div style={cardStyle}>
      <div style={{ padding: 24, flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
          <h3 style={cardTitleStyle}>{restaurant.name}</h3>
          {restaurant.rating && (
            <div style={ratingBadgeStyle}>
              <Star size={12} fill="#1d1d1f" /> <span>{restaurant.rating}</span>
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <span style={pillStyle}>{restaurant.cuisine}</span>
          {restaurant.price_range && <span style={pillStyle}>{restaurant.price_range}</span>}
          {restaurant.area && <span style={secondaryPillStyle}>{restaurant.area}</span>}
        </div>

        <p style={descriptionStyle}>{restaurant.why_recommended}</p>

        {(restaurant.hours_text || restaurant.phone || restaurant.address) && (
          <div style={metaContainerStyle}>
            {restaurant.hours_text && (
              <div style={metaItemStyle}>
                <Clock size={14} /> <span>{restaurant.hours_text}</span>
              </div>
            )}
            {restaurant.address && (
              <div style={metaItemStyle}>
                <MapPin size={14} /> <span>{restaurant.address}</span>
              </div>
            )}
            {restaurant.phone && (
              <div style={metaItemStyle}>
                <Phone size={14} /> <span>{restaurant.phone}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <a href={restaurant.url} target="_blank" rel="noopener noreferrer" style={cardFooterLinkStyle}>
        <span>Visit Website</span>
        <ChevronRight size={16} />
      </a>
    </div>
  );
}

function AttractionCard({ attraction }: { attraction: TravelSpot }) {
  return (
    <div style={cardStyle}>
      <div style={{ padding: 24, flex: 1 }}>
        <h3 style={cardTitleStyle}>{attraction.name}</h3>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <span style={pillStyle}>{attraction.kind}</span>
          {attraction.area && <span style={secondaryPillStyle}>{attraction.area}</span>}
          {attraction.reservation_required && (
            <span style={{ ...pillStyle, background: "#fff0f0", color: "#c62828" }}>
              Reservation Required
            </span>
          )}
        </div>

        <p style={descriptionStyle}>{attraction.why_recommended}</p>

        <div style={metaContainerStyle}>
          {attraction.hours_text && (
            <div style={metaItemStyle}>
              <Clock size={14} /> <span>{attraction.hours_text}</span>
            </div>
          )}
          {attraction.estimated_duration_min && (
            <div style={metaItemStyle}>
              <Clock size={14} /> <span>~{attraction.estimated_duration_min} mins</span>
            </div>
          )}
          {attraction.price_hint && (
            <div style={metaItemStyle}>
              <CreditCard size={14} /> <span>{attraction.price_hint}</span>
            </div>
          )}
        </div>
      </div>

      <a href={attraction.url} target="_blank" rel="noopener noreferrer" style={cardFooterLinkStyle}>
        <span>View Details</span>
        <ChevronRight size={16} />
      </a>
    </div>
  );
}

function HotelCard({ hotel }: { hotel: Hotel }) {
  return (
    <div style={cardStyle}>
      <div style={{ padding: 24, flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <h3 style={cardTitleStyle}>{hotel.name}</h3>
          {hotel.price_per_night && (
            <div style={priceBadgeStyle}>{hotel.price_per_night}<span style={{ fontSize: 12, fontWeight: 400 }}>/night</span></div>
          )}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          {hotel.area && <span style={secondaryPillStyle}>{hotel.area}</span>}
          {hotel.amenities?.slice(0, 3).map((am: string) => (
            <span key={am} style={tertiaryPillStyle}>{am}</span>
          ))}
        </div>

        <p style={descriptionStyle}>{hotel.why_recommended}</p>

        {(hotel.phone || hotel.address) && (
          <div style={metaContainerStyle}>
            {hotel.address && (
              <div style={metaItemStyle}>
                <MapPin size={14} /> <span>{hotel.address}</span>
              </div>
            )}
            {hotel.phone && (
              <div style={metaItemStyle}>
                <Phone size={14} /> <span>{hotel.phone}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <a href={hotel.url} target="_blank" rel="noopener noreferrer" style={cardFooterLinkStyle}>
        <span>Book Now</span>
        <ChevronRight size={16} />
      </a>
    </div>
  );
}

function CarRentalCard({ car }: { car: CarRental }) {
  return (
    <div style={compactCardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <h4 style={subTitleStyle}>{car.provider}</h4>
        {car.price_per_day && <span style={compactPriceStyle}>{car.price_per_day}/day</span>}
      </div>

      <p style={{ fontSize: 15, fontWeight: 500, color: "#1d1d1f", margin: 0 }}>{car.vehicle_class}</p>

      {car.pickup_location && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: 13, color: "#86868b" }}>
          <MapPin size={12} />
          {car.pickup_location}
        </div>
      )}

      <a href={car.url} target="_blank" rel="noopener noreferrer" style={compactLinkStyle}>
        Book Car
      </a>
    </div>
  );
}

function FlightCard({ flight }: { flight: Flight }) {
  return (
    <div style={compactCardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <h4 style={subTitleStyle}>{flight.airline || "Airline"}</h4>
        {flight.price_range && <span style={compactPriceStyle}>{flight.price_range}</span>}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <Plane size={16} color="#FF4F00" />
        <span style={{ fontSize: 15, color: "#1d1d1f", fontWeight: 500 }}>{flight.route}</span>
      </div>

      <span style={tertiaryPillStyle}>{flight.trip_type === "round-trip" ? "Round-trip" : "One-way"}</span>

      <a href={flight.url} target="_blank" rel="noopener noreferrer" style={compactLinkStyle}>
        Check Flights
      </a>
    </div>
  );
}

// -- Styles --

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
  gap: 24,
  marginTop: 16,
};

const compactGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
  gap: 16,
  marginTop: 16,
};

const subHeaderStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 600,
  color: "#1d1d1f",
  margin: "0 0 16px 0",
};

const cardStyle: React.CSSProperties = {
  background: "#ffffff",
  borderRadius: 24,
  boxShadow: "0 4px 24px rgba(0,0,0,0.04)",
  border: "1px solid rgba(0,0,0,0.04)",
  display: "flex",
  flexDirection: "column",
  transition: "transform 0.2s ease, box-shadow 0.2s ease",
  overflow: "hidden",
};

const cardTitleStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
  color: "#1d1d1f",
  margin: 0,
  lineHeight: 1.3,
};

const descriptionStyle: React.CSSProperties = {
  fontSize: 15,
  color: "#424245",
  lineHeight: 1.6,
  margin: "16px 0 0 0",
};

const pillStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "5px 12px",
  fontSize: 12,
  fontWeight: 600,
  color: "#1d1d1f",
  background: "#f5f5f7",
  borderRadius: 100,
  letterSpacing: "0.01em",
};

const secondaryPillStyle: React.CSSProperties = {
  ...pillStyle,
  background: "transparent",
  border: "1px solid #e5e5ea",
  color: "#6e6e73",
};

const tertiaryPillStyle: React.CSSProperties = {
  ...pillStyle,
  fontSize: 11,
  background: "#f5f5f7",
  color: "#6e6e73",
};

const ratingBadgeStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 4,
  fontSize: 13,
  fontWeight: 600,
  background: "#f5f5f7",
  padding: "4px 8px",
  borderRadius: 8,
};

const priceBadgeStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 600,
  color: "#1d1d1f",
};

const metaContainerStyle: React.CSSProperties = {
  marginTop: 20,
  paddingTop: 16,
  borderTop: "1px solid #f5f5f7",
  display: "flex",
  flexDirection: "column",
  gap: 8,
};

const metaItemStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  fontSize: 13,
  color: "#86868b",
  fontWeight: 500,
};

const cardFooterLinkStyle: React.CSSProperties = {
  marginTop: "auto",
  padding: "16px 24px",
  background: "#fafafa",
  borderTop: "1px solid #f5f5f7",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  fontSize: 14,
  fontWeight: 600,
  textDecoration: "none",
  transition: "background 0.2s",
  color: "#FF4F00",
};

// Compact Cards (Transport)
const compactCardStyle: React.CSSProperties = {
  background: "#ffffff",
  borderRadius: 16,
  padding: 20,
  boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
  border: "1px solid rgba(0,0,0,0.04)",
  display: "flex",
  flexDirection: "column",
};

const subTitleStyle: React.CSSProperties = {
  fontSize: 16,
  fontWeight: 700,
  color: "#1d1d1f",
  margin: 0,
  lineHeight: 1.3,
};

const compactPriceStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: "#1d8b3a",
};

const compactLinkStyle: React.CSSProperties = {
  marginTop: 16,
  fontSize: 14,
  fontWeight: 600,
  color: "#FF4F00",
  textDecoration: "none",
};

const exportButtonStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  padding: "10px 20px",
  fontSize: 14,
  fontWeight: 600,
  color: "#1d1d1f",
  background: "#f5f5f7",
  border: "1px solid #e5e5ea",
  borderRadius: 100,
  textDecoration: "none",
  transition: "all 0.2s ease",
  cursor: "pointer",
};

// Reference rows
const refRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  padding: "10px 16px",
  borderRadius: 10,
  background: "#fafafa",
  fontSize: 14,
};

const refNameStyle: React.CSSProperties = {
  fontWeight: 600,
  color: "#1d1d1f",
  minWidth: 0,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
  maxWidth: 220,
};

const refDetailStyle: React.CSSProperties = {
  color: "#86868b",
  flex: 1,
  minWidth: 0,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const refPriceStyle: React.CSSProperties = {
  fontWeight: 600,
  color: "#1d8b3a",
  whiteSpace: "nowrap",
};

const refLinkStyle: React.CSSProperties = {
  fontWeight: 600,
  color: "#FF4F00",
  textDecoration: "none",
  whiteSpace: "nowrap",
  marginLeft: "auto",
};
