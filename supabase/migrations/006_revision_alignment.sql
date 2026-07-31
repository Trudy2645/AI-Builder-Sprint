alter table public.revision_request_items
    drop constraint revision_request_items_request_type_check,
    drop constraint revision_request_items_requested_text_check,
    alter column requested_text drop not null;

alter table public.revision_request_items
    add constraint revision_request_items_request_type_check
        check (request_type in ('modify', 'delete', 'add')),
    add constraint revision_request_items_shape_check check (
        (request_type = 'modify' and clause_id is not null
            and requested_text is not null and btrim(requested_text) <> '')
        or (request_type = 'delete' and clause_id is not null and requested_text is null)
        or (request_type = 'add' and clause_id is null
            and requested_text is not null and btrim(requested_text) <> '')
    );

alter table public.revision_requests
    add column decision_message text,
    add column response_message text,
    add column responded_at timestamptz;

create table public.revision_request_item_documents (
    revision_request_item_id uuid not null
        references public.revision_request_items(id) on delete cascade,
    document_id uuid not null references public.documents(id) on delete restrict,
    created_at timestamptz not null default timezone('utc', now()),
    primary key (revision_request_item_id, document_id)
);

create function public.validate_revision_item_clause_version()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    expected_version_id uuid;
    actual_version_id uuid;
begin
    if new.clause_id is null then
        return new;
    end if;

    select rr.contract_version_id into expected_version_id
    from public.revision_requests rr
    where rr.id = new.revision_request_id;

    select cc.contract_version_id into actual_version_id
    from public.contract_clauses cc
    where cc.id = new.clause_id;

    if expected_version_id is null or actual_version_id is distinct from expected_version_id then
        raise exception 'revision item clause must belong to its base contract version'
            using errcode = '23514';
    end if;
    return new;
end;
$$;

create trigger revision_item_clause_version_check
before insert or update of revision_request_id, clause_id on public.revision_request_items
for each row execute function public.validate_revision_item_clause_version();

create function public.validate_revision_item_document_owner()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    expected_contract_id uuid;
    actual_contract_id uuid;
begin
    select rr.contract_id into expected_contract_id
    from public.revision_request_items ri
    join public.revision_requests rr on rr.id = ri.revision_request_id
    where ri.id = new.revision_request_item_id;

    select d.contract_id into actual_contract_id
    from public.documents d
    where d.id = new.document_id;

    if expected_contract_id is null or actual_contract_id is distinct from expected_contract_id then
        raise exception 'revision item document must belong to the same contract'
            using errcode = '23514';
    end if;
    return new;
end;
$$;

create trigger revision_item_document_owner_check
before insert or update on public.revision_request_item_documents
for each row execute function public.validate_revision_item_document_owner();

create index revision_item_documents_document_idx
    on public.revision_request_item_documents (document_id);

alter table public.revision_request_item_documents enable row level security;

create policy revision_item_documents_select_party
on public.revision_request_item_documents
for select to authenticated
using (
    exists (
        select 1
        from public.revision_request_items ri
        join public.revision_requests rr on rr.id = ri.revision_request_id
        where ri.id = revision_request_item_documents.revision_request_item_id
          and public.can_access_contract(rr.contract_id)
    )
);

grant select, insert, update, delete
on public.revision_request_item_documents to authenticated;

comment on table public.revision_request_item_documents is
    'Existing contract-owned documents attached to an individual revision request item.';
