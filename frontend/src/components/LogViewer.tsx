import React, { useState, useEffect, useRef, useCallback } from 'react';

interface LogEntry {
  timestamp: string;
  source: string;
  level: string;
  message: string;
}

const LEVEL_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  ERROR:   { bg: 'rgba(239,68,68,0.15)', color: '#f87171', label: 'ERR' },
  WARNING: { bg: 'rgba(245,158,11,0.12)', color: '#fbbf24', label: 'WRN' },
  INFO:    { bg: 'transparent',           color: '#94a3b8', label: 'INF' },
  DEBUG:   { bg: 'transparent',           color: '#4b5563', label: 'DBG' },
};

const SOURCE_COLORS: Record<string, string> = {
  'agents.langgraph_brain': '#a78bfa',
  'agents.analyst_orchestrator': '#60a5fa',
  'agents.pattern_agent': '#34d399',
  'agents.quant_agent': '#f472b6',
  'agents.sentiment_agent': '#fbbf24',
  'agents.analyst_brain': '#c084fc',
  'root': '#6b7280',
};

function getSourceColor(source: string): string {
  return SOURCE_COLORS[source] || '#8b95a5';
}

function shortenSource(source: string): string {
  // agents.langgraph_brain → LangGraphBrain
  if (source.startsWith('agents.')) {
    return source
      .replace('agents.', '')
      .split('_')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join('');
  }
  return source;
}

export default function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [levelFilter, setLevelFilter] = useState<string>('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [total, setTotal] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Load initial logs
  const fetchLogs = useCallback(async () => {
    try {
      const params = new URLSearchParams({ lines: '200' });
      if (levelFilter) params.set('level', levelFilter);
      const res = await fetch(`http://127.0.0.1:8000/logs/recent?${params}`);
      const data = await res.json();
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  }, [levelFilter]);

  // Start SSE streaming
  const startStreaming = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource('http://127.0.0.1:8000/logs/stream');
    eventSourceRef.current = es;
    setStreaming(true);

    es.onmessage = (event) => {
      try {
        const entry: LogEntry = JSON.parse(event.data);
        if (levelFilter && entry.level !== levelFilter) return;
        if (['httpx', 'uvicorn.access'].includes(entry.source)) return;

        setLogs(prev => {
          const updated = [...prev, entry];
          // Keep only last 500 in memory
          return updated.length > 500 ? updated.slice(-500) : updated;
        });
        setTotal(prev => prev + 1);
      } catch {}
    };

    es.onerror = () => {
      setStreaming(false);
      es.close();
    };
  }, [levelFilter]);

  const stopStreaming = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setStreaming(false);
  }, []);

  // Fetch on open / filter change
  useEffect(() => {
    if (expanded) {
      fetchLogs();
      startStreaming();
    } else {
      stopStreaming();
    }
    return () => stopStreaming();
  }, [expanded, levelFilter]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 40;
    setAutoScroll(isAtBottom);
  };

  const levelCounts = logs.reduce((acc, l) => {
    acc[l.level] = (acc[l.level] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(10,15,28,0.98) 0%, rgba(15,23,42,0.95) 100%)',
      border: '1px solid rgba(99,102,241,0.15)',
      borderRadius: 12,
      overflow: 'hidden',
      marginTop: '1rem',
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    }}>
      {/* Header */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.6rem 1rem',
          cursor: 'pointer',
          userSelect: 'none',
          borderBottom: expanded ? '1px solid rgba(255,255,255,0.06)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: 14 }}>📋</span>
          <span style={{
            fontSize: 13,
            fontWeight: 700,
            color: '#e2e8f0',
            letterSpacing: '0.03em',
          }}>
            System Logs
          </span>
          {streaming && (
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: '#22c55e',
              display: 'inline-block',
              animation: 'pulse 2s infinite',
              marginLeft: 4,
            }} />
          )}
          {!expanded && (
            <span style={{ fontSize: 11, color: '#6b7280', marginLeft: '0.25rem' }}>
              {total} entries
              {(levelCounts['WARNING'] || 0) > 0 && ` · ${levelCounts['WARNING']} warnings`}
              {(levelCounts['ERROR'] || 0) > 0 && ` · ${levelCounts['ERROR']} errors`}
            </span>
          )}
        </div>
        <span style={{
          color: '#6b7280',
          fontSize: 14,
          transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
          transition: 'transform 0.2s',
        }}>▾</span>
      </div>

      {/* Body */}
      {expanded && (
        <>
          {/* Toolbar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.5rem 1rem',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            flexWrap: 'wrap',
          }}>
            {/* Level filters */}
            {['', 'INFO', 'WARNING', 'ERROR'].map(lvl => (
              <button
                key={lvl || 'ALL'}
                onClick={() => setLevelFilter(lvl)}
                style={{
                  padding: '0.2rem 0.6rem',
                  fontSize: 11,
                  fontWeight: 600,
                  borderRadius: 4,
                  border: levelFilter === lvl
                    ? '1px solid rgba(99,102,241,0.6)'
                    : '1px solid rgba(255,255,255,0.08)',
                  background: levelFilter === lvl
                    ? 'rgba(99,102,241,0.2)'
                    : 'transparent',
                  color: levelFilter === lvl ? '#a5b4fc' : '#6b7280',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {lvl || 'ALL'}
                {lvl && levelCounts[lvl] ? ` (${levelCounts[lvl]})` : ''}
              </button>
            ))}

            <div style={{ flex: 1 }} />

            <span style={{ fontSize: 10, color: '#4b5563' }}>
              {logs.length} shown / {total} total
            </span>

            <button
              onClick={() => { fetchLogs(); }}
              style={{
                padding: '0.2rem 0.5rem',
                fontSize: 11,
                background: 'transparent',
                color: '#6b7280',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 4,
                cursor: 'pointer',
              }}
            >
              ↻ Refresh
            </button>
          </div>

          {/* Log entries */}
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            style={{
              maxHeight: 400,
              overflowY: 'auto',
              padding: '0.25rem 0',
              fontSize: 12,
              lineHeight: '1.6',
            }}
          >
            {logs.length === 0 && (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#4b5563' }}>
                No logs available
              </div>
            )}
            {logs.map((entry, i) => {
              const style = LEVEL_STYLES[entry.level] || LEVEL_STYLES.DEBUG;
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    gap: '0.5rem',
                    padding: '0.15rem 1rem',
                    background: style.bg,
                    borderLeft: entry.level === 'ERROR' ? '3px solid #ef4444'
                      : entry.level === 'WARNING' ? '3px solid #f59e0b'
                      : '3px solid transparent',
                    transition: 'background 0.2s',
                  }}
                >
                  {/* Timestamp */}
                  <span style={{ color: '#4b5563', flexShrink: 0, width: 60 }}>
                    {entry.timestamp ? entry.timestamp.split(' ')[1] : ''}
                  </span>

                  {/* Level badge */}
                  <span style={{
                    color: style.color,
                    fontWeight: 700,
                    flexShrink: 0,
                    width: 28,
                    fontSize: 10,
                    letterSpacing: '0.05em',
                  }}>
                    {style.label}
                  </span>

                  {/* Source */}
                  <span style={{
                    color: getSourceColor(entry.source),
                    flexShrink: 0,
                    width: 130,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontSize: 11,
                  }}>
                    {shortenSource(entry.source)}
                  </span>

                  {/* Message */}
                  <span style={{
                    color: entry.level === 'ERROR' ? '#fca5a5'
                      : entry.level === 'WARNING' ? '#fde68a'
                      : '#cbd5e1',
                    flex: 1,
                    wordBreak: 'break-word',
                  }}>
                    {entry.message}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Footer */}
          {!autoScroll && (
            <div style={{
              textAlign: 'center',
              padding: '0.35rem',
              borderTop: '1px solid rgba(255,255,255,0.06)',
            }}>
              <button
                onClick={() => {
                  setAutoScroll(true);
                  if (scrollRef.current) {
                    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
                  }
                }}
                style={{
                  fontSize: 11,
                  color: '#6366f1',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                ↓ Jump to bottom
              </button>
            </div>
          )}
        </>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
