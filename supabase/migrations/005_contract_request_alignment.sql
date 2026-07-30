alter table public.contracts
    add column request_message text,
    add column initial_request_kind text not null default 'as_is',
    add constraint contracts_initial_request_kind_check
        check (initial_request_kind in ('as_is', 'revision'));

comment on column public.contracts.request_message is
    'Buyer message captured when the contract request is created.';
comment on column public.contracts.initial_request_kind is
    'Initial buyer intent: accept listing terms as-is or request revision.';
