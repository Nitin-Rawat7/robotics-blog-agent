'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type BlogResult = {
  success: boolean;
  title?: string;
  content?: string;
  source_link?: string;
  error?: string;
};

const LOG_STAGES = [
  'connecting to sources...',
  'scanning RSS feeds...',
  'filtering for relevance...',
  'candidates collected',
  'selecting lead story...',
  'drafting report...',
  'finalizing copy...',
];

export default function Home() {
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [log, setLog] = useState<string[]>([]);
  const [result, setResult] = useState<BlogResult | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const generate = async () => {
    setStatus('running');
    setResult(null);
    setLog([]);

    let stageIndex = 0;
    timerRef.current = setInterval(() => {
      if (stageIndex < LOG_STAGES.length) {
        setLog((prev) => [...prev, LOG_STAGES[stageIndex]]);
        stageIndex += 1;
      }
    }, 1400);

    try {
      const res = await fetch(`${API_URL}/generate-blog`, { method: 'POST' });
      const data: BlogResult = await res.json();

      if (timerRef.current) clearInterval(timerRef.current);

      if (data.success) {
        setLog((prev) => [...prev, 'report filed.']);
        setResult(data);
        setStatus('done');
      } else {
        setLog((prev) => [...prev, `failed: ${data.error || 'unknown error'}`]);
        setStatus('error');
      }
    } catch (err) {
      if (timerRef.current) clearInterval(timerRef.current);
      setLog((prev) => [...prev, 'failed: could not reach backend']);
      setStatus('error');
    }
  };

  return (
    <main style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px 32px',
          borderBottom: '1px solid var(--grid)',
        }}
      >
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 13,
            letterSpacing: '0.12em',
            color: 'var(--muted)',
          }}
        >
          ROBOTICS&nbsp;DESK <span style={{ color: 'var(--grid)' }}>/</span> AUTOMATED FIELD REPORT
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12,
            color: 'var(--muted)',
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              backgroundColor: status === 'running' ? 'var(--amber)' : 'var(--teal)',
              boxShadow:
                status === 'running'
                  ? '0 0 8px var(--amber)'
                  : '0 0 8px var(--teal)',
              transition: 'all 0.3s ease',
            }}
          />
          SYSTEM: {status === 'running' ? 'FILING' : 'READY'}
        </div>
      </header>

      {/* Hero */}
      <section
        style={{
          flex: '0 0 auto',
          padding: '72px 32px 48px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'relative',
            padding: '48px 64px',
            border: '1px solid var(--grid)',
          }}
        >
          {[
            { top: -1, left: -1, borderTop: '2px solid var(--amber)', borderLeft: '2px solid var(--amber)' },
            { top: -1, right: -1, borderTop: '2px solid var(--amber)', borderRight: '2px solid var(--amber)' },
            { bottom: -1, left: -1, borderBottom: '2px solid var(--amber)', borderLeft: '2px solid var(--amber)' },
            { bottom: -1, right: -1, borderBottom: '2px solid var(--amber)', borderRight: '2px solid var(--amber)' },
          ].map((s, i) => (
            <span
              key={i}
              style={{
                position: 'absolute',
                width: 18,
                height: 18,
                ...s,
              }}
            />
          ))}

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 24 }}>
            <button
              onClick={generate}
              disabled={status === 'running'}
              aria-label="Generate a new robotics field report"
              style={{
                width: 96,
                height: 96,
                borderRadius: '50%',
                border: '3px solid var(--amber)',
                backgroundColor: status === 'running' ? 'var(--panel)' : 'var(--amber)',
                color: status === 'running' ? 'var(--amber)' : 'var(--navy)',
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 700,
                fontSize: 13,
                letterSpacing: '0.05em',
                cursor: status === 'running' ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: status === 'running' ? 'none' : '0 0 24px rgba(255,138,61,0.35)',
              }}
              onMouseEnter={(e) => {
                if (status !== 'running') e.currentTarget.style.transform = 'scale(1.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >
              {status === 'running' ? 'WORKING' : 'GENERATE'}
            </button>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 12,
                color: 'var(--muted)',
                textAlign: 'center',
              }}
            >
              one click files one report,<br />sourced from live robotics news
            </div>
          </div>
        </div>

        {log.filter(Boolean).length > 0 && (
          <div
            style={{
              marginTop: 32,
              width: '100%',
              maxWidth: 480,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
              color: 'var(--teal)',
              lineHeight: 1.9,
            }}
          >
            {log.filter(Boolean).map((line, i) => (
              <div key={i} style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--grid)' }}>{String(i + 1).padStart(2, '0')}</span>
                <span style={{ color: line.startsWith('failed') ? '#FF6B6B' : 'var(--teal)' }}>
                  {line}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {result?.success && (
        <section
          style={{
            flex: 1,
            borderTop: '1px solid var(--grid)',
            backgroundColor: 'var(--panel)',
            padding: '56px 24px 96px',
          }}
        >
          <article
            style={{
              maxWidth: 680,
              margin: '0 auto',
              backgroundColor: 'var(--navy)',
              border: '1px solid var(--grid)',
              padding: '48px 56px',
            }}
          >
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 12,
                color: 'var(--amber)',
                letterSpacing: '0.1em',
                marginBottom: 24,
              }}
            >
              FIELD REPORT &middot;{' '}
              {new Date().toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              }).toUpperCase()}
            </div>

            <div
              className="article-body"
              style={{
                fontFamily: "'Source Serif 4', serif",
                fontSize: 17,
                lineHeight: 1.75,
                color: 'var(--paper)',
              }}
            >
              <ReactMarkdown
                components={{
                  h1: ({ children }) => (
                    <h1
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: 32,
                        fontWeight: 700,
                        lineHeight: 1.25,
                        marginBottom: 16,
                        color: 'var(--paper)',
                      }}
                    >
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: 21,
                        fontWeight: 600,
                        marginTop: 36,
                        marginBottom: 12,
                        color: 'var(--amber)',
                      }}
                    >
                      {children}
                    </h2>
                  ),
                  p: ({ children }) => <p style={{ marginBottom: 18 }}>{children}</p>,
                  ul: ({ children }) => (
                    <ul style={{ marginBottom: 18, paddingLeft: 22 }}>{children}</ul>
                  ),
                  li: ({ children }) => <li style={{ marginBottom: 8 }}>{children}</li>,
                  hr: () => (
                    <hr
                      style={{
                        border: 'none',
                        borderTop: '1px dashed var(--grid)',
                        margin: '32px 0 16px',
                      }}
                    />
                  ),
                  em: ({ children }) => (
                    <em
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontStyle: 'normal',
                        fontSize: 13,
                        color: 'var(--muted)',
                      }}
                    >
                      {children}
                    </em>
                  ),
                  a: ({ children, href }) => (
                    <a href={href} style={{ color: 'var(--teal)' }} target="_blank" rel="noreferrer">
                      {children}
                    </a>
                  ),
                }}
              >
                {result.content}
              </ReactMarkdown>
            </div>
          </article>
        </section>
      )}
    </main>
  );
}