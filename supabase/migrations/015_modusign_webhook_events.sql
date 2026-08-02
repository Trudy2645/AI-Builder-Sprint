create table public.modusign_webhook_events (
    id uuid primary key default gen_random_uuid(),
    provider_event_id text not null unique,
    provider_document_id text not null,
    received_at timestamptz not null default timezone('utc', now()),
    processed_at timestamptz,
    status text not null default 'received' check (status in ('received', 'processed', 'failed'))
);

create index modusign_webhook_events_document_idx
    on public.modusign_webhook_events (provider_document_id, received_at desc);
