# RAG Knowledge Ingestion Pipeline

## Document Sources
- Policy documents (TEXT/PDF/DOCX via ingest_document)
- Website URLs (via web_scraper.ingest_website)

## Web Ingestion Flow
1. Validate URL (block private networks, check robots.txt)
2. Fetch HTML with custom User-Agent
3. Extract title, headings, body text (strip nav/scripts/ads)
4. Chunk into 800-char segments with 120-char overlap
5. Embed using sentence-transformers/all-MiniLM-L6-v2 (local, CPU)
6. Store in ChromaDB (collection: yottaflex_policies)
7. Track status in rag_web_sources + rag_ingestion_jobs tables

## Safety Rules
- Private networks blocked: 127.x, 192.168.x, 10.x, localhost
- robots.txt respected
- Max 50,000 chars extracted per page
- Only text/html and text/plain content types accepted
- 15s request timeout
