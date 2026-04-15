import React, { useState, useEffect } from 'react';

interface QuantWeightsProps {
  weights: Record<string, number>;  // e.g. {momentum: 40, volume: 35, volatility: 25}
  onChange: (weights: Record<string, number>) => void;
  disabled?: boolean;
}

const LABELS: Record<string, string> = {
  momentum: 'Momentum (RSI)',
  volume: 'Volume',
  volatility: 'Volatility (BB)',
};

const COLORS: Record<string, string> = {
  momentum: '#60a5fa',
  volume: '#34d399',
  volatility: '#fbbf24',
};

export const DEFAULT_QUANT_WEIGHTS: Record<string, number> = {
  momentum: 40,
  volume: 35,
  volatility: 25,
};

export default function QuantWeights({ weights, onChange, disabled }: QuantWeightsProps) {
  const [localWeights, setLocalWeights] = useState<Record<string, number>>(weights);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setLocalWeights(weights);
  }, [weights]);

  const total = Object.values(localWeights).reduce((a, b) => a + b, 0);

  const handleSliderChange = (key: string, value: number) => {
    const updated = { ...localWeights, [key]: value };
    setLocalWeights(updated);
  };

  const handleApply = () => {
    // Normalize to decimals for API
    const t = Object.values(localWeights).reduce((a, b) => a + b, 0);
    const normalized: Record<string, number> = {};
    for (const [k, v] of Object.entries(localWeights)) {
      normalized[k] = t > 0 ? v / t : 0.25;
    }
    onChange(normalized);
  };

  const handleReset = () => {
    setLocalWeights({ ...DEFAULT_QUANT_WEIGHTS });
    // Also apply the reset immediately
    onChange({
      momentum: 0.40,
      volume: 0.35,
      volatility: 0.25,
    });
  };

  const keys = Object.keys(LABELS);

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 100%)',
      border: '1px solid rgba(99,102,241,0.2)',
      borderRadius: 12,
      padding: expanded ? '1rem 1.25rem 1.25rem' : '0.6rem 1.25rem',
      marginBottom: '1rem',
      transition: 'all 0.3s ease',
    }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setExpanded(e => !e)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: 14 }}>⚖️</span>
          <span style={{
            fontSize: 13,
            fontWeight: 700,
            color: '#f1f5f9',
            letterSpacing: '0.02em',
          }}>
            Quant Indicator Weights
          </span>
          {!expanded && (
            <span style={{ fontSize: 11, color: '#6b7280', fontWeight: 500, marginLeft: '0.25rem' }}>
              {keys.map(k => `${LABELS[k].split(' ')[0]} ${localWeights[k]}%`).join(' · ')}
            </span>
          )}
        </div>
        <span style={{
          color: '#6b7280',
          fontSize: 14,
          transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
          transition: 'transform 0.2s',
          display: 'inline-block',
        }}>
          ▾
        </span>
      </div>

      {/* Body */}
      {expanded && (
        <div style={{ marginTop: '0.75rem' }}>
          {/* Weight bar visualization */}
          <div style={{
            display: 'flex',
            height: 8,
            borderRadius: 4,
            overflow: 'hidden',
            marginBottom: '1rem',
            background: '#1f2937',
          }}>
            {keys.map(key => (
              <div
                key={key}
                style={{
                  width: `${total > 0 ? (localWeights[key] / total) * 100 : 25}%`,
                  background: COLORS[key],
                  transition: 'width 0.2s ease',
                }}
                title={`${LABELS[key]}: ${localWeights[key]}%`}
              />
            ))}
          </div>

          {/* Sliders */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {keys.map(key => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: COLORS[key],
                  flexShrink: 0,
                }} />
                <span style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#e2e8f0',
                  width: 130,
                  flexShrink: 0,
                }}>
                  {LABELS[key]}
                </span>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={localWeights[key]}
                  onChange={e => handleSliderChange(key, Number(e.target.value))}
                  disabled={disabled}
                  style={{
                    flex: 1,
                    accentColor: COLORS[key],
                    cursor: disabled ? 'not-allowed' : 'pointer',
                  }}
                />
                <span style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: COLORS[key],
                  width: 36,
                  textAlign: 'right',
                  flexShrink: 0,
                }}>
                  {total > 0 ? Math.round((localWeights[key] / total) * 100) : 25}%
                </span>
              </div>
            ))}
          </div>

          {/* Total + buttons */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginTop: '0.75rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid rgba(255,255,255,0.06)',
          }}>
            <span style={{ fontSize: 11, color: '#6b7280' }}>
              Raw total: {total} → normalized to 100%
            </span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={handleReset}
                disabled={disabled}
                style={{
                  padding: '0.35rem 0.75rem',
                  background: 'transparent',
                  color: '#94a3b8',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                Reset Defaults
              </button>
              <button
                onClick={handleApply}
                disabled={disabled}
                style={{
                  padding: '0.35rem 0.9rem',
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                Apply & Re-analyze
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
