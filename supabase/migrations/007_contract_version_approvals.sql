create table public.contract_version_approvals (
    id uuid primary key default gen_random_uuid(),
    contract_version_id uuid not null
        references public.contract_versions(id) on delete restrict,
    party_role public.party_role not null,
    approved_by_user_id uuid not null references auth.users(id) on delete restrict,
    approved_at timestamptz not null default timezone('utc', now()),
    created_at timestamptz not null default timezone('utc', now()),
    unique (contract_version_id, party_role)
);

create index contract_version_approvals_user_idx
    on public.contract_version_approvals (approved_by_user_id, approved_at desc);

create trigger contract_version_approvals_immutable
before update or delete on public.contract_version_approvals
for each row execute function public.prevent_immutable_change();

alter table public.contract_version_approvals enable row level security;

create policy contract_version_approvals_select_party
on public.contract_version_approvals
for select to authenticated
using (
    exists (
        select 1
        from public.contract_versions cv
        where cv.id = contract_version_approvals.contract_version_id
          and public.can_access_contract(cv.contract_id)
    )
);

grant select, insert on public.contract_version_approvals to authenticated;

comment on table public.contract_version_approvals is
    'Immutable buyer and seller approvals scoped to one exact contract version.';
