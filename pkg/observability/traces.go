package observability

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"strings"
	"sync"
	"time"

	_ "github.com/lib/pq"
	"github.com/sipeed/picoclaw/pkg/logger"
)

type runContextKey struct{}
type iterationContextKey struct{}

type ToolEvent struct {
	Tool       string                 `json:"tool"`
	Args       map[string]any         `json:"args,omitempty"`
	Iteration  int                    `json:"iteration"`
	DurationMS int64                  `json:"duration_ms,omitempty"`
	IsError    bool                   `json:"is_error"`
	ErrorMsg   string                 `json:"error_msg,omitempty"`
	Extra      map[string]interface{} `json:"extra,omitempty"`
}

type Run struct {
	ID         string
	Gateway    string
	Sender     string
	Subject    string
	SessionKey string
	Persona    string
	StartedAt  float64

	mu         sync.Mutex
	toolEvents []ToolEvent
	errorCount int
}

func WithRun(ctx context.Context, run *Run) context.Context {
	if run == nil {
		return ctx
	}
	return context.WithValue(ctx, runContextKey{}, run)
}

func RunFromContext(ctx context.Context) (*Run, bool) {
	run, ok := ctx.Value(runContextKey{}).(*Run)
	return run, ok && run != nil
}

func WithIteration(ctx context.Context, iteration int) context.Context {
	return context.WithValue(ctx, iterationContextKey{}, iteration)
}

func IterationFromContext(ctx context.Context) int {
	v := ctx.Value(iterationContextKey{})
	if n, ok := v.(int); ok {
		return n
	}
	return 0
}

func (r *Run) appendToolEvent(ev ToolEvent) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.toolEvents = append(r.toolEvents, ev)
	if ev.IsError {
		r.errorCount++
	}
}

func (r *Run) snapshot() ([]ToolEvent, int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	cp := make([]ToolEvent, len(r.toolEvents))
	copy(cp, r.toolEvents)
	return cp, r.errorCount
}

type TraceWriter struct {
	enabled bool
	db      *sql.DB
}

var (
	globalWriter *TraceWriter
	once         sync.Once
)

func GlobalTraceWriter() *TraceWriter {
	once.Do(func() {
		globalWriter = newTraceWriterFromEnv()
	})
	return globalWriter
}

func newTraceWriterFromEnv() *TraceWriter {
	dsn := strings.TrimSpace(os.Getenv("PICOCLAW_TRACES_DB_URL"))
	if dsn == "" {
		return &TraceWriter{enabled: false}
	}
	dsn = ensurePostgresSSLMode(dsn)

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		logger.WarnCF("observability", "Failed to open traces DB", map[string]any{"error": err.Error()})
		return &TraceWriter{enabled: false}
	}
	db.SetMaxOpenConns(6)
	db.SetMaxIdleConns(3)
	db.SetConnMaxIdleTime(2 * time.Minute)
	db.SetConnMaxLifetime(30 * time.Minute)

	pingCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if err := db.PingContext(pingCtx); err != nil {
		_ = db.Close()
		logger.WarnCF("observability", "Traces DB ping failed", map[string]any{"error": err.Error()})
		return &TraceWriter{enabled: false}
	}

	w := &TraceWriter{enabled: true, db: db}
	if err := w.ensureSchema(); err != nil {
		logger.WarnCF("observability", "Failed to ensure traces schema", map[string]any{"error": err.Error()})
		_ = db.Close()
		return &TraceWriter{enabled: false}
	}
	logger.InfoC("observability", "Runtime tracing enabled")
	return w
}

func (w *TraceWriter) Enabled() bool {
	return w != nil && w.enabled && w.db != nil
}

func (w *TraceWriter) ensureSchema() error {
	if !w.Enabled() {
		return nil
	}
	stmts := []string{
		`CREATE TABLE IF NOT EXISTS traces (
			task_id     TEXT PRIMARY KEY,
			gateway     TEXT,
			sender      TEXT,
			preview     TEXT,
			exit_code   INTEGER,
			started_at  DOUBLE PRECISION NOT NULL,
			ended_at    DOUBLE PRECISION,
			duration_ms INTEGER,
			tool_count  INTEGER DEFAULT 0,
			error_count INTEGER DEFAULT 0,
			tools_json  TEXT DEFAULT '[]'
		)`,
		`CREATE TABLE IF NOT EXISTS tool_events (
			id          BIGSERIAL PRIMARY KEY,
			task_id     TEXT NOT NULL,
			persona     TEXT,
			tool        TEXT NOT NULL,
			args_json   TEXT,
			iteration   INTEGER,
			status      TEXT NOT NULL DEFAULT 'running',
			duration_ms INTEGER,
			result_len  INTEGER,
			error       TEXT,
			started_at  DOUBLE PRECISION NOT NULL
		)`,
		`CREATE INDEX IF NOT EXISTS idx_tool_events_task_id ON tool_events (task_id)`,
		`CREATE INDEX IF NOT EXISTS idx_tool_events_started_at ON tool_events (started_at)`,
		`CREATE INDEX IF NOT EXISTS idx_tool_events_persona ON tool_events (persona) WHERE persona IS NOT NULL`,
		`CREATE TABLE IF NOT EXISTS run_events (
			id          BIGSERIAL PRIMARY KEY,
			task_id     TEXT NOT NULL,
			persona     TEXT,
			event_type  TEXT NOT NULL,
			payload_json TEXT,
			status      TEXT NOT NULL DEFAULT 'ok',
			duration_ms INTEGER,
			error       TEXT,
			created_at  DOUBLE PRECISION NOT NULL
		)`,
		`CREATE INDEX IF NOT EXISTS idx_run_events_task_id ON run_events (task_id)`,
		`CREATE INDEX IF NOT EXISTS idx_run_events_created_at ON run_events (created_at)`,
	}
	for _, stmt := range stmts {
		var err error
		for attempt := 0; attempt < 3; attempt++ {
			_, err = w.db.Exec(stmt)
			if err == nil {
				break
			}
			if !isSchemaRaceError(err) {
				return err
			}
			time.Sleep(50 * time.Millisecond)
		}
		if err != nil && !isSchemaRaceError(err) {
			return err
		}
	}
	return nil
}

func (w *TraceWriter) RecordToolEvent(run *Run, ev ToolEvent, resultLen int) {
	if !w.Enabled() || run == nil {
		return
	}
	argsJSON, _ := json.Marshal(ev.Args)
	status := "done"
	if ev.IsError {
		status = "error"
	}
	startedAt := float64(time.Now().UnixMilli()) / 1000.0
	_, err := w.db.Exec(
		`INSERT INTO tool_events
		  (task_id, persona, tool, args_json, iteration, status, duration_ms, result_len, error, started_at)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
		run.ID,
		run.Persona,
		ev.Tool,
		string(argsJSON),
		ev.Iteration,
		status,
		ev.DurationMS,
		resultLen,
		nullIfEmpty(ev.ErrorMsg),
		startedAt,
	)
	if err != nil {
		logger.WarnCF("observability", "Failed to insert tool_event", map[string]any{
			"task_id": run.ID,
			"tool":    ev.Tool,
			"error":   err.Error(),
		})
		return
	}
	run.appendToolEvent(ev)
}

func (w *TraceWriter) RecordContextEvent(run *Run, payload map[string]any, iteration int) {
	if !w.Enabled() || run == nil || payload == nil {
		return
	}
	argsJSON, _ := json.Marshal(payload)
	startedAt := float64(time.Now().UnixMilli()) / 1000.0
	_, err := w.db.Exec(
		`INSERT INTO tool_events
		  (task_id, persona, tool, args_json, iteration, status, duration_ms, result_len, error, started_at)
		 VALUES ($1,$2,'__context__',$3,$4,'done',0,0,NULL,$5)`,
		run.ID,
		run.Persona,
		string(argsJSON),
		iteration,
		startedAt,
	)
	if err != nil {
		logger.WarnCF("observability", "Failed to insert context_event", map[string]any{
			"task_id": run.ID,
			"error":   err.Error(),
		})
	}
}

func (w *TraceWriter) RecordRunEvent(run *Run, eventType string, payload map[string]any, status string, durationMS int64, eventErr string) {
	if !w.Enabled() || run == nil || strings.TrimSpace(eventType) == "" {
		return
	}
	if status == "" {
		status = "ok"
	}
	payloadJSON, _ := json.Marshal(payload)
	createdAt := float64(time.Now().UnixMilli()) / 1000.0
	_, err := w.db.Exec(
		`INSERT INTO run_events
		  (task_id, persona, event_type, payload_json, status, duration_ms, error, created_at)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
		run.ID,
		run.Persona,
		eventType,
		string(payloadJSON),
		status,
		durationMS,
		nullIfEmpty(eventErr),
		createdAt,
	)
	if err != nil {
		logger.WarnCF("observability", "Failed to insert run_event", map[string]any{
			"task_id":    run.ID,
			"event_type": eventType,
			"error":      err.Error(),
		})
	}
}

func (w *TraceWriter) FinishRun(run *Run, exitCode int) {
	if !w.Enabled() || run == nil {
		return
	}
	endedAt := float64(time.Now().UnixMilli()) / 1000.0
	durationMS := int((endedAt - run.StartedAt) * 1000)
	if durationMS < 0 {
		durationMS = 0
	}
	toolEvents, errorCount := run.snapshot()
	toolsJSON, _ := json.Marshal(toolEvents)
	_, err := w.db.Exec(
		`INSERT INTO traces
		  (task_id, gateway, sender, preview, exit_code, started_at, ended_at, duration_ms, tool_count, error_count, tools_json)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
		 ON CONFLICT (task_id) DO UPDATE SET
		   gateway=EXCLUDED.gateway,
		   sender=EXCLUDED.sender,
		   preview=EXCLUDED.preview,
		   exit_code=EXCLUDED.exit_code,
		   started_at=EXCLUDED.started_at,
		   ended_at=EXCLUDED.ended_at,
		   duration_ms=EXCLUDED.duration_ms,
		   tool_count=EXCLUDED.tool_count,
		   error_count=EXCLUDED.error_count,
		   tools_json=EXCLUDED.tools_json`,
		run.ID,
		run.Gateway,
		run.Sender,
		run.Subject,
		exitCode,
		run.StartedAt,
		endedAt,
		durationMS,
		len(toolEvents),
		errorCount,
		string(toolsJSON),
	)
	if err != nil {
		logger.WarnCF("observability", "Failed to upsert trace row", map[string]any{
			"task_id": run.ID,
			"error":   err.Error(),
		})
	}
}

func nullIfEmpty(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

func ensurePostgresSSLMode(dsn string) string {
	if strings.Contains(strings.ToLower(dsn), "sslmode=") {
		return dsn
	}
	if strings.Contains(dsn, "://") {
		if strings.Contains(dsn, "?") {
			return dsn + "&sslmode=disable"
		}
		return dsn + "?sslmode=disable"
	}
	return dsn + " sslmode=disable"
}

func isSchemaRaceError(err error) bool {
	if err == nil {
		return false
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "pg_type_typname_nsp_index") ||
		(strings.Contains(msg, "duplicate key value violates unique constraint") && strings.Contains(msg, "pg_type")) ||
		strings.Contains(msg, "already exists")
}
