import React, { useState, useEffect, useRef, KeyboardEvent } from 'react';
import { Search } from 'lucide-react';

interface TickerAutocompleteProps {
  value: string;
  onChange: (val: string) => void;
  onSelect: (val: string) => void;
  disabled?: boolean;
}

export default function TickerAutocomplete({ value, onChange, onSelect, disabled }: TickerAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [allTickers, setAllTickers] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch all tickers from config on mount
  useEffect(() => {
    fetch('http://localhost:8000/top_stocks')
      .then(res => res.json())
      .then(data => {
        if (data.tickers && Array.isArray(data.tickers)) {
          setAllTickers(data.tickers);
        }
      })
      .catch(err => console.error("Failed to load ticker list", err));
  }, []);

  // Handle click outside to close suggestions
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [wrapperRef]);

  // Filter suggestions when input changes
  useEffect(() => {
    if (!value) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    
    // Only show suggestions when focused
    if (document.activeElement === inputRef.current) {
        const filtered = allTickers.filter(t => 
            t.toLowerCase().startsWith(value.toLowerCase())
        );
        
        // Hide if it's an exact match
        if (filtered.length === 1 && filtered[0].toLowerCase() === value.toLowerCase()) {
            setSuggestions([]);
            setShowSuggestions(false);
        } else {
            setSuggestions(filtered);
            setShowSuggestions(filtered.length > 0);
        }
        setActiveIndex(-1); // Reset highlight when typing
    }
  }, [value, allTickers]);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    // If no suggestions, behave normally
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter') {
          // If they just hit enter on a random typed string, we want the form to submit
          // The form's onSubmit will catch this naturally because it's an Enter key in an input
          setShowSuggestions(false);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(prev => (prev > 0 ? prev - 1 : prev));
    } else if (e.key === 'Enter') {
      // If a suggestion is highlighted, prevent default form submit and use the suggestion
      if (activeIndex >= 0 && activeIndex < suggestions.length) {
        e.preventDefault(); // Stop the form from submitting with incomplete query
        const selected = suggestions[activeIndex];
        onChange(selected);
        setShowSuggestions(false);
        onSelect(selected); // Trigger analysis immediately
      } else {
        // No item highlighted, allow form to submit
        setShowSuggestions(false);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    onChange(suggestion);
    setShowSuggestions(false);
    onSelect(suggestion); // Trigger analysis immediately
    inputRef.current?.focus();
  };

  const handleFocus = () => {
      // Show suggestions immediately on focus if there's text
      if (value) {
          const filtered = allTickers.filter(t => 
              t.toLowerCase().startsWith(value.toLowerCase())
          );
          // Hide if it's an exact match
          if (filtered.length === 1 && filtered[0].toLowerCase() === value.toLowerCase()) {
              setSuggestions([]);
              setShowSuggestions(false);
          } else {
              setSuggestions(filtered);
              setShowSuggestions(filtered.length > 0);
          }
      }
  }

  return (
    <div className="search-input-group" ref={wrapperRef}>
      <Search className="search-icon" size={20} />
      <input
        ref={inputRef}
        type="text"
        placeholder="Enter Stock Ticker (e.g., NVDA)"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={handleFocus}
        disabled={disabled}
        className="search-input"
        autoComplete="off"
      />
      
      {showSuggestions && suggestions.length > 0 && (
        <ul className="autocomplete-dropdown">
          {suggestions.map((suggestion, index) => (
            <li
              key={suggestion}
              className={`autocomplete-item ${index === activeIndex ? 'active' : ''}`}
              onClick={() => handleSuggestionClick(suggestion)}
              onMouseEnter={() => setActiveIndex(index)}
            >
              {suggestion}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
