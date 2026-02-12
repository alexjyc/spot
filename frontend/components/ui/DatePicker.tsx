"use client";

import * as React from "react";
import { format } from "date-fns";
import { Calendar as CalendarIcon, X } from "lucide-react";
import { DayPicker } from "react-day-picker";

interface DatePickerProps {
    selected?: Date;
    onSelect: (date: Date | undefined) => void;
    placeholder?: string;
    minDate?: Date;
    hasError?: boolean;
}

export function DatePicker({
    selected,
    onSelect,
    placeholder = "Pick a date",
    minDate,
    hasError = false,
}: DatePickerProps) {
    const [isOpen, setIsOpen] = React.useState(false);
    const containerRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (
                containerRef.current &&
                !containerRef.current.contains(event.target as Node)
            ) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, []);

    const handleSelect = (date: Date | undefined) => {
        onSelect(date);
        setIsOpen(false);
    };

    const handleClear = (e: React.MouseEvent) => {
        e.stopPropagation();
        onSelect(undefined);
    };

    return (
        <div
            ref={containerRef}
            style={{ position: "relative", width: "100%" }}
        >
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                style={{
                    width: "100%",
                    padding: "16px 20px",
                    textAlign: "left",
                    background: "#ffffff",
                    border: hasError ? "1px solid #ff3b30" : isOpen ? "2px solid #000" : "1px solid #e5e5ea",
                    borderRadius: "14px",
                    fontSize: "16px",
                    color: selected ? "#1d1d1f" : "#86868b",
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                    outline: "none",
                    fontWeight: 500,
                    boxShadow: isOpen
                        ? "0 4px 12px rgba(0,0,0,0.08)"
                        : "0 1px 2px rgba(0,0,0,0.04)",
                }}
            >
                <CalendarIcon size={18} color={selected ? "#1d1d1f" : "#86868b"} />
                <span style={{ flex: 1 }}>
                    {selected ? format(selected, "MMM dd, yyyy") : placeholder}
                </span>
                {selected && (
                    <div
                        role="button"
                        onClick={handleClear}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: 20,
                            height: 20,
                            borderRadius: "50%",
                            background: "#e5e5ea",
                            color: "#86868b",
                        }}
                    >
                        <X size={12} />
                    </div>
                )}
            </button>

            {isOpen && (
                <div
                    style={{
                        position: "absolute",
                        top: "calc(100% + 8px)",
                        left: 0,
                        zIndex: 50,
                        background: "white",
                        borderRadius: "16px",
                        boxShadow:
                            "0 12px 32px rgba(0, 0, 0, 0.12), 0 4px 8px rgba(0, 0, 0, 0.04)",
                        border: "1px solid rgba(0,0,0,0.05)",
                        padding: "16px",
                        animation: "fadeIn 0.2s ease-out",
                    }}
                >
                    <DayPicker
                        mode="single"
                        selected={selected}
                        onSelect={handleSelect}
                        showOutsideDays
                        fromDate={minDate}
                        modifiersClassNames={{
                            selected: "rdp-day_selected",
                        }}
                    />
                </div>
            )}
        </div>
    );
}
