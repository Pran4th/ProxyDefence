# Sequence Diagrams

## Standard Copilot Query

```
User                  Copilot Router         Copilot Service       Intelligence Agent    LLM Client          Tool Layer           Existing API
 |                          |                       |                     |                    |                   |                      |
 |-- POST /copilot/query -->|                       |                     |                    |                   |                      |
 |                          |-- service.query() --->|                     |                    |                   |                      |
 |                          |                       |-- agent.run() ---->|                    |                   |                      |
 |                          |                       |                     |-- chat() --------->|                   |                      |
 |                          |                       |                     |<-- tool_calls -----|                   |                      |
 |                          |                       |                     |-- execute() --------------------------->|                      |
 |                          |                       |                     |                    |                   |-- GET /endpoint ---->|
 |                          |                       |                     |                    |                   |<-- response ---------|
 |                          |                       |                     |<-- ToolResult -----|                   |                      |
 |                          |                       |                     |-- chat() --------->|                   |                      |
 |                          |                       |                     |<-- response -------|                   |                      |
 |                          |                       |<-- AgentResponse ---|                    |                   |                      |
 |                          |<-- result ------------|                     |                    |                   |                      |
 |<-- JSON Response --------|                       |                     |                    |                   |                      |
```

## Streaming Copilot Query

```
User                  Copilot Router         Copilot Service       Intelligence Agent    LLM Client
 |                          |                       |                     |                    |
 |-- POST /copilot/query/stream -->|                 |                     |                    |
 |                          |                       |-- query_stream() -->|                    |
 |                          |                       |                     |-- run_stream() --->|
 |                          |                       |                     |-- chat(stream) --->|
 |                          |                       |                     |<-- tokens ---------| (streamed)
 |                          |                       |<-- events ----------|                    |
 |                          |<-- SSE stream --------|                     |                    |
 |<-- data: {"type":"token","value":"..."} ---------|                     |                    |
 |<-- data: {"type":"tool_call",...} ---------------|                     |                    |
 |<-- data: {"type":"tool_result",...} -------------|                     |                    |
 |<-- data: {"type":"citation",...} ----------------|                     |                    |
 |<-- data: {"type":"confidence",...} --------------|                     |                    |
 |<-- data: {"type":"metadata",...} ----------------|                     |                    |
 |<-- data: {"type":"done"} ------------------------|                     |                    |
```

## RAG Retrieval Flow

```
Agent               RAG Engine            Retriever           Elasticsearch      pgvector           Energy KG
 |                       |                    |                     |                 |                   |
 |-- retrieve(query) --->|                    |                     |                 |                   |
 |                       |-- hybrid_search() -|                     |                 |                   |
 |                       |                    |-- dense_retrieval ->|                 |                   |
 |                       |                    |                     |                 |-- vector search ->|
 |                       |                    |                     |<-- results -----|                   |
 |                       |                    |-- sparse_retrieval -|-- BM25 search ->|                   |
 |                       |                    |                     |<-- results -----|                   |
 |                       |                    |-- kg_expansion -----|                 |                   |
 |                       |                    |                     |                 |                   |-- graph query ->
 |                       |                    |                     |                 |                   |
 |                       |                    |<-- fused results ---|                 |                   |
 |                       |<-- context --------|                     |                 |                   |
 |<-- context_text ------|                    |                     |                 |                   |
```
