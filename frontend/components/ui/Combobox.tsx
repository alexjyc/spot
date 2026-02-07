"use client";

import * as React from "react";
import { Check, ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface ComboboxProps {
    value: string;
    onChange: (value: string) => void;
    options?: string[];
    placeholder?: string;
    icon?: React.ReactNode;
    hasError?: boolean;
}

const DEFAULT_OPTIONS = [
    "New York (JFK)",
    "London (LHR)",
    "Paris (CDG)",
    "Tokyo (NRT)",
    "Dubai (DXB)",
    "Singapore (SIN)",
    "Los Angeles (LAX)",
    "Seoul (ICN)",
    "Barcelona (BCN)",
    "Rome (FCO)",
    "Miami (MIA)",
    "San Francisco (SFO)",
    "Sydney (SYD)",
    "Berlin (BER)",
    "Amsterdam (AMS)",
];

export function Combobox({
    value,
    onChange,
    options = DEFAULT_OPTIONS,
    placeholder = "Select...",
    icon,
    hasError
}: ComboboxProps) {
    const [isOpen, setIsOpen] = React.useState(false);
    const [search, setSearch] = React.useState("");
    const containerRef = React.useRef<HTMLDivElement>(null);
    const inputRef = React.useRef<HTMLInputElement>(null);

    // Close when clicking outside
    React.useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Update search when value changes externally (or initial)
    React.useEffect(() => {
        // Only update search if it doesn't match the current value (prevents cursor jumping if we were typing)
        if (value && !isOpen) {
            setSearch(value);
        }
    }, [value, isOpen]);

    const filteredOptions = options.filter((opt) =>
        opt.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div
            ref={containerRef}
            style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                background: "#ffffff",
                border: hasError ? "1px solid #ff3b30" : isOpen ? "1px solid #FF4F00" : "1px solid #e5e5ea",
                boxShadow: hasError
                    ? "0 0 0 2px rgba(255, 59, 48, 0.1)"
                    : isOpen
                        ? "0 4px 12px rgba(255, 79, 0, 0.1)"
                        : "none",
                borderRadius: "14px",
                padding: "0 16px",
                height: "54px",
                position: "relative", // For dropdown positioning
                transition: "all 0.2s ease",
            }}
        >
            {icon}
            <input
                ref={inputRef}
                placeholder={placeholder}
                value={isOpen ? search : value || search} // Show search text while open, value when closed
                onChange={(e) => {
                    setSearch(e.target.value);
                    onChange(e.target.value); // Allow free text
                    if (!isOpen) setIsOpen(true);
                }}
                onFocus={() => {
                    setIsOpen(true);
                    setSearch(value); // Prime search with current value on focus
                }}
                style={{
                    flex: 1,
                    padding: "16px 0",
                    fontSize: "16px",
                    border: "none",
                    outline: "none",
                    fontFamily: "inherit",
                    backgroundColor: "transparent",
                    fontWeight: 500,
                    color: "#1d1d1f",
                }}
            />
            <ChevronDown
                size={16}
                color="#86868b"
                style={{
                    transition: "transform 0.2s ease",
                    transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
                }}
            />

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 8, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 8, scale: 0.98 }}
                        transition={{ duration: 0.2, ease: "easeOut" }}
                        style={{
                            position: "absolute",
                            top: "calc(100% + 8px)",
                            left: 0,
                            right: 0,
                            background: "#ffffff",
                            borderRadius: "16px",
                            boxShadow: "0 10px 40px rgba(0,0,0,0.1), 0 2px 10px rgba(0,0,0,0.05)",
                            border: "1px solid #f5f5f7",
                            padding: "8px",
                            zIndex: 100,
                            maxHeight: "300px",
                            overflowY: "auto",
                        }}
                    >
                        {filteredOptions.length > 0 ? (
                            filteredOptions.map((opt) => (
                                <div
                                    key={opt}
                                    onClick={() => {
                                        onChange(opt);
                                        setSearch(opt);
                                        setIsOpen(false);
                                    }}
                                    style={{
                                        padding: "10px 12px",
                                        borderRadius: "8px",
                                        cursor: "pointer",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "space-between",
                                        fontSize: "15px",
                                        color: "#1d1d1f",
                                        transition: "background 0.1s",
                                    }}
                                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f5f5f7")}
                                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                                >
                                    {opt}
                                    {value === opt && <Check size={16} color="#FF4F00" />}
                                </div>
                            ))
                        ) : (
                            <div
                                style={{
                                    padding: "12px",
                                    fontSize: "14px",
                                    color: "#86868b",
                                    textAlign: "center",
                                }}
                            >
                                Use "{search}"
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
