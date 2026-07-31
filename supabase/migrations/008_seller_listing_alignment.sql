alter table public.listing_terms
    add column people_per_unit integer,
    add column no_show_policy text,
    add column termination_policy text,
    add column special_terms text,
    add constraint listing_terms_people_per_unit_check
        check (people_per_unit is null or people_per_unit > 0);

create index contracts_listing_id_idx
    on public.contracts (listing_id)
    where listing_id is not null;

comment on column public.listing_terms.people_per_unit is
    'Explicit capacity per billable unit; never inferred by the server.';
comment on column public.listing_terms.no_show_policy is
    'Optional no-show policy captured in the listing terms snapshot.';
comment on column public.listing_terms.termination_policy is
    'Optional contract termination policy captured in the listing terms snapshot.';
comment on column public.listing_terms.special_terms is
    'Optional special terms captured in the listing terms snapshot.';
