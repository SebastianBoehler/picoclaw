package hooks

import (
	"context"
	"sync"
)

type ToolInvocation struct {
	Name    string
	Args    map[string]any
	Channel string
	ChatID  string
}

type ToolOutcome struct {
	IsError bool
	ForLLM  string
	ForUser string
	Async   bool
}

type OutboundMessage struct {
	Channel string
	ChatID  string
	Content string
}

type BeforeToolHook func(ctx context.Context, in ToolInvocation) (ToolInvocation, error)
type AfterToolHook func(ctx context.Context, in ToolInvocation, out ToolOutcome)
type BeforeOutboundHook func(ctx context.Context, msg OutboundMessage) (OutboundMessage, error)
type ErrorHook func(ctx context.Context, stage string, err error, meta map[string]any)

type Manager struct {
	mu             sync.RWMutex
	beforeTool     []BeforeToolHook
	afterTool      []AfterToolHook
	beforeOutbound []BeforeOutboundHook
	onError        []ErrorHook
}

func NewManager() *Manager {
	return &Manager{}
}

func NewDefaultManager() *Manager {
	m := NewManager()
	guard := NewSecretLeakGuard()
	m.RegisterBeforeTool(guard.BeforeTool)
	m.RegisterBeforeOutbound(guard.BeforeOutbound)
	return m
}

func (m *Manager) RegisterBeforeTool(h BeforeToolHook) {
	if m == nil || h == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.beforeTool = append(m.beforeTool, h)
}

func (m *Manager) RegisterAfterTool(h AfterToolHook) {
	if m == nil || h == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.afterTool = append(m.afterTool, h)
}

func (m *Manager) RegisterBeforeOutbound(h BeforeOutboundHook) {
	if m == nil || h == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.beforeOutbound = append(m.beforeOutbound, h)
}

func (m *Manager) RegisterOnError(h ErrorHook) {
	if m == nil || h == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.onError = append(m.onError, h)
}

func (m *Manager) RunBeforeTool(ctx context.Context, in ToolInvocation) (ToolInvocation, error) {
	if m == nil {
		return in, nil
	}
	m.mu.RLock()
	hooks := append([]BeforeToolHook(nil), m.beforeTool...)
	m.mu.RUnlock()
	cur := in
	var err error
	for _, h := range hooks {
		cur, err = h(ctx, cur)
		if err != nil {
			m.EmitError(ctx, "before_tool", err, map[string]any{"tool": in.Name})
			return cur, err
		}
	}
	return cur, nil
}

func (m *Manager) RunAfterTool(ctx context.Context, in ToolInvocation, out ToolOutcome) {
	if m == nil {
		return
	}
	m.mu.RLock()
	hooks := append([]AfterToolHook(nil), m.afterTool...)
	m.mu.RUnlock()
	for _, h := range hooks {
		h(ctx, in, out)
	}
}

func (m *Manager) RunBeforeOutbound(ctx context.Context, msg OutboundMessage) (OutboundMessage, error) {
	if m == nil {
		return msg, nil
	}
	m.mu.RLock()
	hooks := append([]BeforeOutboundHook(nil), m.beforeOutbound...)
	m.mu.RUnlock()
	cur := msg
	var err error
	for _, h := range hooks {
		cur, err = h(ctx, cur)
		if err != nil {
			m.EmitError(ctx, "before_outbound", err, map[string]any{
				"channel": msg.Channel,
				"chat_id": msg.ChatID,
			})
			return cur, err
		}
	}
	return cur, nil
}

func (m *Manager) EmitError(ctx context.Context, stage string, err error, meta map[string]any) {
	if m == nil || err == nil {
		return
	}
	m.mu.RLock()
	hooks := append([]ErrorHook(nil), m.onError...)
	m.mu.RUnlock()
	for _, h := range hooks {
		h(ctx, stage, err, meta)
	}
}
