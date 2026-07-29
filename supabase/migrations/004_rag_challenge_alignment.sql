create type public.ai_job_status as enum ('queued', 'processing', 'succeeded', 'failed');
create type public.finding_severity as enum ('high', 'medium', 'low', 'none');
create type public.finding_importance as enum ('high', 'medium', 'low');
create type public.finding_status as enum ('open', 'applied', 'dismissed');
create type public.grounding_status as enum ('grounded', 'insufficient_evidence', 'not_required');
create type public.knowledge_corpus_type as enum ('official', 'template');
create type public.knowledge_base_status as enum ('active', 'inactive');
create type public.knowledge_version_status as enum (
    'discovered', 'downloaded', 'normalized', 'reviewed',
    'uploaded', 'indexed', 'active', 'failed', 'superseded', 'revoked'
);

create table public.ai_jobs (
    id uuid primary key default gen_random_uuid(),
    document_id uuid references public.documents(id) on delete restrict,
    listing_version_id uuid references public.listing_versions(id) on delete restrict,
    contract_version_id uuid references public.contract_versions(id) on delete restrict,
    job_type text not null,
    status public.ai_job_status not null default 'queued',
    idempotency_key text not null,
    provider text not null default 'upstage',
    model_name text,
    prompt_version text,
    attempt_count integer not null default 0 check (attempt_count >= 0),
    provider_status text,
    failure_code text,
    failure_message text,
    result_metadata jsonb not null default '{}'::jsonb,
    queued_at timestamptz not null default timezone('utc', now()),
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (idempotency_key),
    constraint ai_jobs_target_check check (
        num_nonnulls(document_id, listing_version_id, contract_version_id) >= 1
    ),
    constraint ai_jobs_completion_check check (
        status not in ('succeeded', 'failed') or completed_at is not null
    )
);

create table public.ai_analysis_runs (
    id uuid primary key default gen_random_uuid(),
    ai_job_id uuid references public.ai_jobs(id) on delete set null,
    listing_version_id uuid references public.listing_versions(id) on delete restrict,
    contract_version_id uuid references public.contract_versions(id) on delete restrict,
    viewer_role public.party_role not null,
    analysis_type text not null,
    model_name text not null,
    prompt_version text not null,
    input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
    knowledge_base_version text,
    status public.ai_job_status not null default 'queued',
    token_usage jsonb not null default '{}'::jsonb,
    latency_ms integer check (latency_ms is null or latency_ms >= 0),
    provider_request_id text,
    created_at timestamptz not null default timezone('utc', now()),
    completed_at timestamptz,
    constraint ai_analysis_runs_target_check check (
        num_nonnulls(listing_version_id, contract_version_id) = 1
    )
);

create table public.ai_findings (
    id uuid primary key default gen_random_uuid(),
    analysis_run_id uuid not null references public.ai_analysis_runs(id) on delete restrict,
    listing_clause_id uuid references public.listing_clauses(id) on delete restrict,
    contract_clause_id uuid references public.contract_clauses(id) on delete restrict,
    category text not null,
    severity public.finding_severity not null,
    importance public.finding_importance not null,
    title text not null,
    explanation text not null,
    suggested_text text,
    suggested_text_sha256 text
        check (suggested_text_sha256 is null or suggested_text_sha256 ~ '^[0-9a-f]{64}$'),
    grounding_status public.grounding_status not null,
    confidence numeric(5, 4) check (confidence is null or confidence between 0 and 1),
    source_location jsonb not null default '{}'::jsonb,
    evidence jsonb not null default '[]'::jsonb,
    disclaimer text not null,
    status public.finding_status not null default 'open',
    dismissed_reason text,
    applied_version_id uuid,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint ai_findings_clause_check check (
        num_nonnulls(listing_clause_id, contract_clause_id) <= 1
    ),
    constraint ai_findings_suggestion_hash_check check (
        suggested_text is null or suggested_text_sha256 is not null
    ),
    constraint ai_findings_dismissed_reason_check check (
        status <> 'dismissed' or dismissed_reason is not null
    )
);

create table public.knowledge_bases (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    corpus_type public.knowledge_corpus_type not null,
    upstage_vector_store_id text,
    status public.knowledge_base_status not null default 'inactive',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table public.knowledge_documents (
    id uuid primary key default gen_random_uuid(),
    knowledge_base_id uuid not null
        references public.knowledge_bases(id) on delete restrict,
    source_key text not null,
    title text not null,
    source_type text not null,
    authority text,
    source_url text,
    jurisdiction text not null default 'KR',
    language public.supported_locale not null default 'ko-KR',
    contract_categories public.contract_category[] not null,
    activity_subtypes text[] not null default '{}'::text[],
    party_type text not null default 'B2C_individual',
    applicability_note text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (knowledge_base_id, source_key),
    constraint knowledge_documents_categories_check check (
        cardinality(contract_categories) > 0
    )
);

create table public.knowledge_document_versions (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null
        references public.knowledge_documents(id) on delete restrict,
    version_label text not null,
    effective_from date,
    effective_to date,
    retrieved_at timestamptz not null,
    content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
    storage_object_path text not null,
    normalized_object_path text,
    upstage_file_id text,
    status public.knowledge_version_status not null default 'discovered',
    approved_by uuid references auth.users(id) on delete set null,
    approved_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    unique (document_id, version_label),
    unique (content_sha256),
    unique (storage_object_path),
    constraint knowledge_versions_effective_period_check check (
        effective_from is null or effective_to is null or effective_from <= effective_to
    ),
    constraint knowledge_versions_approval_check check (
        status not in ('reviewed', 'uploaded', 'indexed', 'active')
        or (approved_by is not null and approved_at is not null)
    )
);

create unique index knowledge_document_versions_one_active_idx
    on public.knowledge_document_versions (document_id)
    where status = 'active';

create table public.rag_retrieval_runs (
    id uuid primary key default gen_random_uuid(),
    analysis_run_id uuid not null
        references public.ai_analysis_runs(id) on delete restrict,
    knowledge_base_id uuid not null
        references public.knowledge_bases(id) on delete restrict,
    query text not null,
    filters jsonb not null default '{}'::jsonb,
    knowledge_base_version text,
    top_k integer not null check (top_k between 1 and 5),
    provider_request_id text,
    result_count integer check (result_count is null or result_count >= 0),
    created_at timestamptz not null default timezone('utc', now())
);

create table public.rag_evidence (
    id uuid primary key default gen_random_uuid(),
    retrieval_run_id uuid not null
        references public.rag_retrieval_runs(id) on delete restrict,
    finding_id uuid not null references public.ai_findings(id) on delete restrict,
    document_version_id uuid not null
        references public.knowledge_document_versions(id) on delete restrict,
    rank integer not null check (rank > 0),
    score numeric(8, 7) check (score is null or score between 0 and 1),
    page_start integer not null check (page_start > 0),
    page_end integer not null check (page_end >= page_start),
    section_path text,
    excerpt text not null check (btrim(excerpt) <> ''),
    bbox jsonb,
    chunk_id text,
    content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default timezone('utc', now()),
    unique (finding_id, rank),
    unique (finding_id, document_version_id, page_start, chunk_id)
);

create table public.localized_contents (
    id uuid primary key default gen_random_uuid(),
    listing_version_id uuid references public.listing_versions(id) on delete restrict,
    contract_version_id uuid references public.contract_versions(id) on delete restrict,
    finding_id uuid references public.ai_findings(id) on delete restrict,
    locale public.supported_locale not null,
    content_type text not null,
    content jsonb not null,
    source_hash text not null check (source_hash ~ '^[0-9a-f]{64}$'),
    prompt_version text not null,
    model_name text not null,
    numeric_validation_passed boolean not null default false,
    created_at timestamptz not null default timezone('utc', now()),
    constraint localized_contents_target_check check (
        num_nonnulls(listing_version_id, contract_version_id, finding_id) = 1
    )
);

create unique index localized_contents_listing_unique
    on public.localized_contents
        (listing_version_id, locale, content_type, prompt_version, source_hash)
    where listing_version_id is not null;
create unique index localized_contents_contract_unique
    on public.localized_contents
        (contract_version_id, locale, content_type, prompt_version, source_hash)
    where contract_version_id is not null;
create unique index localized_contents_finding_unique
    on public.localized_contents
        (finding_id, locale, content_type, prompt_version, source_hash)
    where finding_id is not null;

create index ai_jobs_status_queued_idx
    on public.ai_jobs (status, queued_at)
    where status in ('queued', 'processing');
create index ai_jobs_document_idx
    on public.ai_jobs (document_id, created_at desc)
    where document_id is not null;
create index ai_analysis_runs_listing_idx
    on public.ai_analysis_runs (listing_version_id, viewer_role, created_at desc)
    where listing_version_id is not null;
create index ai_analysis_runs_contract_idx
    on public.ai_analysis_runs (contract_version_id, viewer_role, created_at desc)
    where contract_version_id is not null;
create index ai_findings_analysis_severity_idx
    on public.ai_findings (analysis_run_id, severity, importance);
create index knowledge_documents_categories_idx
    on public.knowledge_documents using gin (contract_categories);
create index knowledge_document_versions_search_idx
    on public.knowledge_document_versions (status, effective_from, effective_to);
create index rag_retrieval_runs_analysis_idx
    on public.rag_retrieval_runs (analysis_run_id, created_at);
create index rag_evidence_finding_idx
    on public.rag_evidence (finding_id, rank);

create trigger ai_jobs_set_updated_at before update on public.ai_jobs
for each row execute function public.set_updated_at();
create trigger ai_findings_set_updated_at before update on public.ai_findings
for each row execute function public.set_updated_at();
create trigger knowledge_bases_set_updated_at before update on public.knowledge_bases
for each row execute function public.set_updated_at();
create trigger knowledge_documents_set_updated_at before update on public.knowledge_documents
for each row execute function public.set_updated_at();
create function public.protect_knowledge_version_snapshot()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'knowledge_document_versions rows cannot be deleted'
            using errcode = '55000';
    end if;

    if row(
        new.document_id,
        new.version_label,
        new.effective_from,
        new.effective_to,
        new.retrieved_at,
        new.content_sha256,
        new.storage_object_path,
        new.normalized_object_path
    ) is distinct from row(
        old.document_id,
        old.version_label,
        old.effective_from,
        old.effective_to,
        old.retrieved_at,
        old.content_sha256,
        old.storage_object_path,
        old.normalized_object_path
    ) then
        raise exception 'knowledge document snapshot columns are immutable'
            using errcode = '55000';
    end if;

    return new;
end;
$$;
create trigger knowledge_document_versions_protect_snapshot
before update or delete on public.knowledge_document_versions
for each row execute function public.protect_knowledge_version_snapshot();
create trigger rag_retrieval_runs_immutable
before update or delete on public.rag_retrieval_runs
for each row execute function public.prevent_immutable_change();
create trigger rag_evidence_immutable
before update or delete on public.rag_evidence
for each row execute function public.prevent_immutable_change();

alter table public.ai_jobs enable row level security;
alter table public.ai_analysis_runs enable row level security;
alter table public.ai_findings enable row level security;
alter table public.knowledge_bases enable row level security;
alter table public.knowledge_documents enable row level security;
alter table public.knowledge_document_versions enable row level security;
alter table public.rag_retrieval_runs enable row level security;
alter table public.rag_evidence enable row level security;
alter table public.localized_contents enable row level security;

grant select, insert, update, delete on all tables in schema public to authenticated;

comment on table public.rag_evidence is
    'Immutable page-level citations selected from official or approved template documents.';
comment on table public.localized_contents is
    'Validated localization cache keyed by immutable source hash and prompt version.';
