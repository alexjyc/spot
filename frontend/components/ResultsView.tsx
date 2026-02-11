import React from "react";
import {
  Utensils,
  MapPin,
  Building2,
  Car,
  Plane,
  Clock,
  CreditCard,
  ChevronRight,
  Star,
  FileText,
  Table,
  CalendarDays,
  DollarSign,
} from "lucide-react";
import { getExportUrl } from "../lib/api";
import type { SpotOnResults, Restaurant, TravelSpot, Hotel, CarRental, Flight, ItineraryDay } from "../types/api";
import { ReferenceTabs } from "./ReferenceTabs";

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
    references = [],
    report,
  } = results;

  const topRestaurants = restaurants.slice(0, TOP_N_RESTAURANTS);
  const topSpots = travel_spots.slice(0, TOP_N);
  const topHotels = hotels.slice(0, TOP_N);
  const topCars = car_rentals.slice(0, TOP_N);
  const topFlights = flights.slice(0, TOP_N);

  // Helper to map API references to UI items
  const mapRefs = (section: string) =>
    references
      .filter(r => r.section === section)
      .map(r => ({
        url: r.url,
        title: r.title || "Source",
        detail: r.content,
        price: undefined // References from common pool don't usually have price
      }));

  // Prepare categories for the ReferenceTabs
  const referenceCategories = [
    {
      id: "dining",
      label: "Dining",
      items: mapRefs("restaurant")
    },
    {
      id: "stays",
      label: "Stays",
      items: mapRefs("hotel")
    },
    {
      id: "attractions",
      label: "Attractions",
      items: mapRefs("attraction")
    },
    {
      id: "cars",
      label: "Cars",
      items: mapRefs("car")
    },
    {
      id: "transport",
      label: "Transport",
      items: mapRefs("flight")
    }
  ];

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

      {/* Travel Report */}
      {report && report.itinerary && report.itinerary.length > 0 && (
        <section className="animate-fadeIn">
          <SectionHeader
            icon={<CalendarDays size={28} className="text-[#FF4F00]" />}
            title="Your Travel Plan"
            subtitle="A curated 3-day itinerary with daily budget."
          />

          {/* Itinerary Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 24, marginTop: 24 }}>
            {report.itinerary.map((day) => (
              <ItineraryDayCard key={day.day_number} day={day} />
            ))}
          </div>

          {/* Total Budget */}
          <div style={{
            marginTop: 32,
            padding: "20px 24px",
            background: "#f5f5f7",
            borderRadius: 16,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <DollarSign size={20} color="#1d8b3a" />
              <span style={{ fontSize: 16, fontWeight: 600, color: "#1d1d1f" }}>
                Estimated Total Budget
              </span>
            </div>
            <span style={{ fontSize: 20, fontWeight: 700, color: "#1d8b3a" }}>
              {report.total_estimated_budget}
            </span>
          </div>
        </section>
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
        </section>
      )}

      {/* Reference Footer */}
      <ReferenceTabs categories={referenceCategories} />
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

function RestaurantCard({ restaurant }: { restaurant: Restaurant }) {
  const hasLinks = Boolean(restaurant.menu_url || restaurant.reservation_url);
  return (
    <div style={cardStyle}>
      <div style={{ padding: 24, flex: 1, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
          <h3 style={cardTitleStyle}>{restaurant.name}</h3>
          {restaurant.rating && (
            <div style={ratingBadgeStyle}>
              <Star size={12} fill="#1d1d1f" /> <span>{restaurant.rating}</span>
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          {restaurant.cuisine && <span style={pillStyle}>{restaurant.cuisine}</span>}
          {restaurant.price_range && <span style={pillStyle}>{restaurant.price_range}</span>}
          {restaurant.area && <span style={secondaryPillStyle}>{restaurant.area}</span>}
        </div>

        <p style={descriptionStyle}>{restaurant.why_recommended}</p>

        {/* Bottom-pinned section: hours + action chips always align at card bottom */}
        <div style={{ marginTop: "auto", paddingTop: 16 }}>
          {restaurant.operating_hours && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "#86868b", fontWeight: 500 }}>
              <Clock size={14} /> <span>{restaurant.operating_hours}</span>
            </div>
          )}

          {hasLinks && (
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              {restaurant.menu_url && (
                <a href={restaurant.menu_url} target="_blank" rel="noopener noreferrer" style={actionChipStyle}>
                  <FileText size={13} strokeWidth={2.5} />
                  <span>View Menu</span>
                </a>
              )}
              {restaurant.reservation_url && (
                <a href={restaurant.reservation_url} target="_blank" rel="noopener noreferrer" style={actionChipPrimaryStyle}>
                  <span>Reserve a Table</span>
                  <ChevronRight size={14} strokeWidth={2.5} />
                </a>
              )}
            </div>
          )}
        </div>
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
      <div style={{ padding: 24, flex: 1, display: "flex", flexDirection: "column" }}>
        <h3 style={cardTitleStyle}>{attraction.name}</h3>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          {attraction.kind && <span style={pillStyle}>{attraction.kind}</span>}
          {attraction.area && <span style={secondaryPillStyle}>{attraction.area}</span>}
        </div>

        <p style={descriptionStyle}>{attraction.why_recommended}</p>

        <div style={metaContainerStyle}>
          {attraction.operating_hours && (
            <div style={metaItemStyle}>
              <Clock size={14} /> <span>{attraction.operating_hours}</span>
            </div>
          )}
          {attraction.estimated_duration_min && (
            <div style={metaItemStyle}>
              <Clock size={14} /> <span>~{attraction.estimated_duration_min} mins</span>
            </div>
          )}
          {attraction.admission_price && (
            <div style={metaItemStyle}>
              <CreditCard size={14} /> <span>{attraction.admission_price}</span>
            </div>
          )}
        </div>

        {attraction.reservation_url && (
          <div style={{ marginTop: "auto", paddingTop: 16 }}>
            <a href={attraction.reservation_url} target="_blank" rel="noopener noreferrer" style={actionChipPrimaryStyle}>
              <span>Get Tickets</span>
              <ChevronRight size={14} strokeWidth={2.5} />
            </a>
          </div>
        )}
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

      {car.vehicle_class && (
        <p style={{ fontSize: 15, fontWeight: 500, color: "#1d1d1f", margin: 0 }}>
          {car.vehicle_class}
        </p>
      )}

      {car.pickup_location && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: 13, color: "#86868b" }}>
          <MapPin size={12} />
          {car.pickup_location}
        </div>
      )}

      {car.operating_hours && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6, fontSize: 13, color: "#86868b" }}>
          <Clock size={12} />
          {car.operating_hours}
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

function ItineraryDayCard({ day }: { day: ItineraryDay }) {
  const timeIcons: Record<string, React.ReactNode> = {
    morning: <span style={{ fontSize: 16 }}>🌅</span>,
    afternoon: <span style={{ fontSize: 16 }}>☀️</span>,
    evening: <span style={{ fontSize: 16 }}>🌙</span>,
  };

  return (
    <div style={cardStyle}>
      <div style={{ padding: 24, flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h3 style={{ ...cardTitleStyle, fontSize: 18 }}>Day {day.day_number}</h3>
          <span style={tertiaryPillStyle}>{day.date}</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {day.slots.map((slot, idx) => (
            <div key={idx} style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
              paddingBottom: idx < day.slots.length - 1 ? 16 : 0,
              borderBottom: idx < day.slots.length - 1 ? "1px solid #f5f5f7" : "none",
            }}>
              <div style={{ paddingTop: 2, flexShrink: 0 }}>
                {timeIcons[slot.time_of_day] || timeIcons.morning}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#1d1d1f" }}>
                    {slot.item_name}
                  </span>
                  {slot.estimated_cost && (
                    <span style={{ fontSize: 12, fontWeight: 500, color: "#1d8b3a", whiteSpace: "nowrap" }}>
                      {slot.estimated_cost}
                    </span>
                  )}
                </div>
                <p style={{ fontSize: 13, color: "#86868b", margin: "4px 0 0 0", lineHeight: 1.4 }}>
                  {slot.activity}
                </p>
                <span style={{ ...tertiaryPillStyle, marginTop: 6, display: "inline-block" }}>
                  {slot.item_type}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{
        padding: "12px 24px",
        background: "#fafafa",
        borderTop: "1px solid #f5f5f7",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        fontSize: 14,
        fontWeight: 600,
      }}>
        <span style={{ color: "#86868b" }}>Day Total</span>
        <span style={{ color: "#1d8b3a" }}>{day.daily_total}</span>
      </div>
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

const actionChipStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "7px 14px",
  borderRadius: 100,
  background: "#f5f5f7",
  border: "none",
  color: "#1d1d1f",
  fontSize: 13,
  fontWeight: 600,
  textDecoration: "none",
  letterSpacing: "-0.01em",
  transition: "background 0.15s ease",
  cursor: "pointer",
};

const actionChipPrimaryStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  padding: "7px 14px",
  borderRadius: 100,
  background: "#FF4F00",
  border: "none",
  color: "#ffffff",
  fontSize: 13,
  fontWeight: 600,
  textDecoration: "none",
  letterSpacing: "-0.01em",
  transition: "background 0.15s ease",
  cursor: "pointer",
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

