alter type public.knowledge_corpus_type add value if not exists 'case_reference';

alter table public.knowledge_document_versions
    add column if not exists upstage_vector_store_file_id text;

create unique index if not exists knowledge_document_versions_upstage_file_idx
    on public.knowledge_document_versions (upstage_file_id)
    where upstage_file_id is not null;

create index if not exists knowledge_documents_party_category_idx
    on public.knowledge_documents (party_type, knowledge_base_id);

comment on column public.knowledge_document_versions.upstage_vector_store_file_id is
    'Provider attachment id/status handle. Provider temporary download URLs are never stored.';
