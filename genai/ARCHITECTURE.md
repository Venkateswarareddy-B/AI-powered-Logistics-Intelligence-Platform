# GenAI Architecture — YottaFlex

## Provider: Groq + Llama (OpenAI intentionally NOT used)
- Model: llama-3.3-70b-versatile (default)
- Provider class: genai/llm/provider.py > GroqProvider
- Abstraction: get_llm() factory — business logic never imports Groq directly

## Configuration (.env)
GROQ_API_KEY=gsk_...          (get free key at console.groq.com/keys)
GROQ_ENABLED=true
GROQ_MODEL=llama-3.3-70b-versatile

## Without API Key
All features work. AI Assistant and Agent show a clear configuration
message instead of crashing. Demo mode is fully functional.

## System Prompt Rules
1. Never fabricate shipment IDs, ETAs, or carrier data
2. Always ground answers in provided PostgreSQL context
3. Separate verified facts from AI-generated recommendations
4. Flag operational actions as requiring human approval
5. Label synthetic/demo data clearly

## Context Injection Pattern
1. Extract shipment IDs from user message
2. Query live PostgreSQL for operational data
3. Run RAG search for policy knowledge
4. Combine both as context in LLM prompt
5. Return grounded response with source citations
