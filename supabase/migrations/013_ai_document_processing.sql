insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'ai-artifacts',
    'ai-artifacts',
    false,
    52428800,
    array['application/json']
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

comment on table public.ai_jobs is
    'Cost-bearing AI executions. Failed jobs may be retried as a new row while successful immutable target/task/prompt/model jobs are reused.';
