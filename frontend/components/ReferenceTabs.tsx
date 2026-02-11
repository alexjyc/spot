"use client";

import React, { useState, useEffect } from "react";
import { BookOpen, ExternalLink, Globe } from "lucide-react";

interface ReferenceItem {
    url: string;
    title: string;
    detail?: string;
    price?: string;
}

interface ReferenceCategory {
    id: string;
    label: string;
    items: ReferenceItem[];
}

interface ReferenceTabsProps {
    categories: ReferenceCategory[];
}

export function ReferenceTabs({ categories }: ReferenceTabsProps) {
    const activeCategories = categories.filter((c) => c.items && c.items.length > 0);
    const [activeTab, setActiveTab] = useState<string>(activeCategories[0]?.id || "");

    // Fix anti-pattern: Move setState to useEffect instead of during render
    useEffect(() => {
        if (!activeCategories.find((c) => c.id === activeTab) && activeCategories.length > 0) {
            setActiveTab(activeCategories[0].id);
        }
    }, [activeCategories, activeTab]);

    if (activeCategories.length === 0) return null;

    const currentCategory = activeCategories.find((c) => c.id === activeTab);

    return (
        <div style={containerStyle}>
            <div style={headerStyle}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                    <div style={{
                        padding: 12,
                        background: "#fff7ed",
                        borderRadius: "16px",
                        color: "#FF4F00"
                    }}>
                        <BookOpen size={28} />
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
                            Curated Knowledge Base
                        </h2>
                        <p style={{ fontSize: 17, color: "#86868b", margin: 0, fontWeight: 400 }}>
                            Explore additional options and sources we found for your trip.
                        </p>
                    </div>
                </div>

                {/* Tab Navigation */}
                <div style={tabContainerStyle}>
                    {activeCategories.map((cat) => {
                        const isActive = activeTab === cat.id;
                        return (
                            <button
                                key={cat.id}
                                onClick={() => setActiveTab(cat.id)}
                                style={isActive ? activeTabStyle : tabStyle}
                            >
                                {cat.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Tab Content */}
            <div style={contentGridStyle}>
                {currentCategory?.items.map((ref, index) => {
                    let domain = "";
                    try {
                        domain = new URL(ref.url).hostname.replace('www.', '');
                    } catch (e) {
                        domain = ref.url;
                    }
                    const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

                    return (
                        <a
                            key={index}
                            href={ref.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={cardStyle}
                        >
                            <div style={cardHeaderStyle}>
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <img
                                        src={faviconUrl}
                                        alt=""
                                        style={{ width: 16, height: 16, borderRadius: 4, opacity: 0.8 }}
                                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                    />
                                    <span style={domainStyle}>{domain}</span>
                                </div>
                                <ExternalLink size={14} color="#d1d1d6" />
                            </div>

                            <h5 style={cardTitleStyle}>{ref.title || ref.title || "Source Link"}</h5>

                            {ref.detail && <p style={cardDetailStyle}>{ref.detail}</p>}

                            {ref.price && (
                                <div style={priceTagStyle}>{ref.price}</div>
                            )}
                        </a>
                    );
                })}
            </div>
        </div>
    );
}

// -- Styles --

const containerStyle: React.CSSProperties = {
    // Parent grid gap handles spacing now
    // paddingTop: 40, 
    // borderTop: "1px solid #f5f5f7",
    background: "transparent",
};

const headerStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    gap: 24,
    marginBottom: 32,
    flexWrap: "wrap",
};

// Removed old titleStyle and subtitleStyle as they are inline now matching SectionHeader

const tabContainerStyle: React.CSSProperties = {
    display: "flex",
    gap: 8,
    overflowX: "auto",
    paddingBottom: 4,
};

const tabStyle: React.CSSProperties = {
    padding: "8px 20px",
    borderRadius: 100,
    background: "transparent",
    border: "1px solid transparent",
    color: "#86868b",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
    transition: "all 0.2s ease",
};

const activeTabStyle: React.CSSProperties = {
    ...tabStyle,
    background: "#ffffff",
    color: "#FF4F00",
    border: "1px solid rgba(0,0,0,0.04)",
    boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
};

const contentGridStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
    gap: 16,
};

const cardStyle: React.CSSProperties = {
    background: "#ffffff",
    borderRadius: 16,
    border: "1px solid rgba(0,0,0,0.04)",
    boxShadow: "0 2px 8px rgba(0,0,0,0.02)",
    padding: 20,
    textDecoration: "none",
    transition: "transform 0.2s ease, box-shadow 0.2s ease",
    display: "flex",
    flexDirection: "column",
};

const cardHeaderStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
};

const domainStyle: React.CSSProperties = {
    fontSize: 11,
    fontWeight: 700,
    color: "#86868b",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
};

const cardTitleStyle: React.CSSProperties = {
    fontSize: 16,
    fontWeight: 700,
    color: "#1d1d1f",
    margin: "0 0 8px 0",
    lineHeight: 1.3,
};

const cardDetailStyle: React.CSSProperties = {
    fontSize: 14,
    color: "#424245",
    lineHeight: 1.5,
    margin: 0,
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
};

const priceTagStyle: React.CSSProperties = {
    display: "inline-block",
    marginTop: 12,
    padding: "4px 8px",
    background: "#e8f5e9",
    color: "#2e7d32",
    fontSize: 11,
    fontWeight: 700,
    borderRadius: 6,
};
