alter table public.ai_analysis_runs
    add column execution_mode text not null default 'fixed_task',
    add column agent_name text,
    add column max_iterations integer not null default 0,
    add column iterations_used integer not null default 0,
    add column stop_reason text,
    add column execution_metadata jsonb not null default '{}'::jsonb,
    add constraint ai_analysis_runs_execution_mode_check
        check (execution_mode in ('fixed_task', 'single_agent')),
    add constraint ai_analysis_runs_agent_check
        check (
            (execution_mode = 'single_agent' and agent_name = 'contract_review')
            or (execution_mode = 'fixed_task' and agent_name is null)
        ),
    add constraint ai_analysis_runs_iterations_check
        check (
            max_iterations between 0 and 2
            and iterations_used between 0 and max_iterations
        ),
    add constraint ai_analysis_runs_stop_reason_check
        check (
            stop_reason is null
            or stop_reason in (
                'completed', 'max_iterations', 'insufficient_evidence', 'provider_error'
            )
        );

alter table public.ai_findings
    add column is_public boolean not null default false;

create index ai_findings_public_buyer_idx
    on public.ai_findings (analysis_run_id, severity, created_at)
    where is_public = true and status in ('open', 'applied');

comment on column public.ai_analysis_runs.execution_metadata is
    'Non-sensitive Agent tool sequence and schema metadata; never raw contracts or prompts.';
comment on column public.ai_findings.is_public is
    'System-approved buyer finding visibility. Seller analysis is always false.';

