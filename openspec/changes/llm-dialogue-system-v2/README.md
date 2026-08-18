# llm-dialogue-system-v2

V2 LLM dialogue system umbrella change. Child changes will be created and executed in priority order after explicit direction.

## Child change hierarchy

```text
llm-dialogue-system-v2
|
|- P0 conversation-foundation
|  |- conversation-history-core
|  |  |- P0.1 conversation-model-storage
|  |  |- P0.2 conversation-message-write
|  |  `- P0.3 conversation-history-read
|  `- P1.1 conversation-context-builder
|
|- P1 dialogue-runtime
|  `- P1.2 dialogue-basic-chat
|
|- P2 interaction-control
|  |- interaction-proposal-gateway
|  |  |- P2.1 platform-capability-catalog
|  |  |- P2.2 interaction-candidate-recognition
|  |  `- P2.3 interaction-proposal-confirmation
|  `- agent-call-authorization
|     |- P2.4 structured-agent-call-contract
|     |- P2.5 agent-call-policy-validation
|     `- P2.6 controlled-agent-dispatch
|
|- P3 dialogue-agent-integration
|  |- P3.1 dialogue-agent-invocation
|  `- P3.2 dialogue-agent-continuation
|
`- P4 retire-v1-llm-chat
```

## Dependency order

```text
conversation-model-storage
  -> conversation-message-write
  -> conversation-history-read
  -> conversation-context-builder
  -> dialogue-basic-chat

platform-capability-catalog
  -> interaction-candidate-recognition
  -> interaction-proposal-confirmation

structured-agent-call-contract
  -> agent-call-policy-validation
  -> controlled-agent-dispatch

dialogue-basic-chat
  + interaction-proposal-confirmation
  + controlled-agent-dispatch
  -> dialogue-agent-invocation
  -> dialogue-agent-continuation
  -> retire-v1-llm-chat
```

Grouping nodes are roadmap labels. Each named leaf is an independent OpenSpec change with its own future proposal, design, specs, tasks, implementation, verification, and archive lifecycle.
