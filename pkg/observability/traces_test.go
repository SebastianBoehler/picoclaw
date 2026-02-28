package observability

import (
	"errors"
	"testing"
)

func TestEnsurePostgresSSLMode(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{
			name: "url appends query",
			in:   "postgresql://u:p@localhost:5432/db",
			want: "postgresql://u:p@localhost:5432/db?sslmode=disable",
		},
		{
			name: "url appends param",
			in:   "postgresql://u:p@localhost:5432/db?connect_timeout=2",
			want: "postgresql://u:p@localhost:5432/db?connect_timeout=2&sslmode=disable",
		},
		{
			name: "key value appends",
			in:   "host=localhost port=5432 dbname=picoclaw_traces user=picoclaw",
			want: "host=localhost port=5432 dbname=picoclaw_traces user=picoclaw sslmode=disable",
		},
		{
			name: "respects existing sslmode",
			in:   "postgresql://u:p@localhost:5432/db?sslmode=require",
			want: "postgresql://u:p@localhost:5432/db?sslmode=require",
		},
		{
			name: "respects existing sslmode key value",
			in:   "host=localhost dbname=db sslmode=verify-full",
			want: "host=localhost dbname=db sslmode=verify-full",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := ensurePostgresSSLMode(tc.in)
			if got != tc.want {
				t.Fatalf("unexpected dsn\n got: %q\nwant: %q", got, tc.want)
			}
		})
	}
}

func TestIsSchemaRaceError(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want bool
	}{
		{
			name: "pg_type duplicate key race",
			err:  errors.New(`pq: duplicate key value violates unique constraint "pg_type_typname_nsp_index"`),
			want: true,
		},
		{
			name: "already exists",
			err:  errors.New(`pq: relation "tool_events" already exists`),
			want: true,
		},
		{
			name: "other db error",
			err:  errors.New(`pq: permission denied for schema public`),
			want: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := isSchemaRaceError(tc.err)
			if got != tc.want {
				t.Fatalf("unexpected result for %q: got %v want %v", tc.err, got, tc.want)
			}
		})
	}
}
