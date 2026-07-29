alter table public.listing_versions add unique (id, listing_id);
alter table public.contract_versions add unique (id, contract_id);
alter table public.revision_requests add unique (id, contract_id);
alter table public.documents add unique (id, listing_id);
alter table public.documents add unique (id, contract_id);

alter table public.listings
    add constraint listings_current_version_owner_fk
    foreign key (current_version_id, id)
    references public.listing_versions(id, listing_id) on delete restrict;
alter table public.listings
    add constraint listings_hero_document_owner_fk
    foreign key (hero_document_id, id)
    references public.documents(id, listing_id) on delete restrict;
alter table public.listing_versions
    add constraint listing_versions_source_document_owner_fk
    foreign key (source_document_id, listing_id)
    references public.documents(id, listing_id) on delete restrict;
alter table public.contracts
    add constraint contracts_source_listing_version_check
    check (source_listing_version_id is null or listing_id is not null);
alter table public.contracts
    add constraint contracts_source_listing_version_owner_fk
    foreign key (source_listing_version_id, listing_id)
    references public.listing_versions(id, listing_id) on delete restrict;
alter table public.contracts
    add constraint contracts_current_version_owner_fk
    foreign key (current_version_id, id)
    references public.contract_versions(id, contract_id) on delete restrict;
alter table public.revision_requests
    add constraint revision_requests_contract_version_owner_fk
    foreign key (contract_version_id, contract_id)
    references public.contract_versions(id, contract_id) on delete restrict;
alter table public.contract_versions
    add constraint contract_versions_revision_request_owner_fk
    foreign key (created_from_revision_request_id, contract_id)
    references public.revision_requests(id, contract_id) on delete restrict;
alter table public.documents
    add constraint documents_listing_version_owner_fk
    foreign key (listing_version_id, listing_id)
    references public.listing_versions(id, listing_id) on delete restrict;
alter table public.documents
    add constraint documents_contract_version_owner_fk
    foreign key (contract_version_id, contract_id)
    references public.contract_versions(id, contract_id) on delete restrict;
alter table public.signature_requests
    add constraint signature_requests_contract_version_owner_fk
    foreign key (contract_version_id, contract_id)
    references public.contract_versions(id, contract_id) on delete restrict;
alter table public.signature_requests
    add constraint signature_requests_signed_document_owner_fk
    foreign key (signed_document_id, contract_id)
    references public.documents(id, contract_id) on delete restrict;
alter table public.signature_requests
    add constraint signature_requests_audit_document_owner_fk
    foreign key (audit_trail_document_id, contract_id)
    references public.documents(id, contract_id) on delete restrict;

create index listings_public_filter_idx
    on public.listings (status, category, district, published_at desc);
create index listings_popular_idx
    on public.listings (status, popularity_score desc);
create index listings_seller_dashboard_idx
    on public.listings (seller_organization_id, status, updated_at desc);
create index listing_terms_service_period_idx
    on public.listing_terms (service_start_date, service_end_date);
create index listing_terms_base_price_idx
    on public.listing_terms (base_price_amount_minor)
    where base_price_amount_minor is not null;
create index listing_versions_listing_created_idx
    on public.listing_versions (listing_id, created_at desc);
create index listing_clauses_version_order_idx
    on public.listing_clauses (listing_version_id, clause_order);
create index price_estimates_listing_created_idx
    on public.price_estimates (listing_id, created_at desc);
create index contracts_seller_dashboard_idx
    on public.contracts (seller_organization_id, status, updated_at desc);
create index contracts_buyer_mypage_idx
    on public.contracts (buyer_user_id, status, updated_at desc);
create index contract_terms_service_end_date_idx
    on public.contract_terms (service_end_date);
create index contract_versions_contract_created_idx
    on public.contract_versions (contract_id, created_at desc);
create index contract_clauses_version_order_idx
    on public.contract_clauses (contract_version_id, clause_order);
create index revision_requests_contract_status_idx
    on public.revision_requests (contract_id, status, created_at desc);
create index revision_request_items_request_order_idx
    on public.revision_request_items (revision_request_id, item_order);
create index documents_listing_idx
    on public.documents (listing_id, purpose, created_at desc)
    where listing_id is not null;
create index documents_contract_idx
    on public.documents (contract_id, purpose, created_at desc)
    where contract_id is not null;
create index signature_requests_contract_idx
    on public.signature_requests (contract_id, created_at desc);
create index provider_events_unprocessed_idx
    on public.provider_events (received_at)
    where not processed;
create index notifications_user_unread_idx
    on public.notifications (user_id, created_at desc)
    where read_at is null;
create index audit_events_contract_created_idx
    on public.audit_events (contract_id, created_at)
    where contract_id is not null;
create index audit_events_listing_created_idx
    on public.audit_events (listing_id, created_at)
    where listing_id is not null;
create index idempotency_records_expiry_idx
    on public.idempotency_records (expires_at);

create trigger listing_versions_immutable
before update or delete on public.listing_versions
for each row execute function public.prevent_immutable_change();
create trigger listing_clauses_immutable
before update or delete on public.listing_clauses
for each row execute function public.prevent_immutable_change();
create trigger contract_parties_immutable
before update or delete on public.contract_parties
for each row execute function public.prevent_immutable_change();
create trigger contract_versions_immutable
before update or delete on public.contract_versions
for each row execute function public.prevent_immutable_change();
create trigger contract_clauses_immutable
before update or delete on public.contract_clauses
for each row execute function public.prevent_immutable_change();
create trigger audit_events_immutable
before update or delete on public.audit_events
for each row execute function public.prevent_immutable_change();

create function public.is_organization_member(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.organization_members as member
        where member.organization_id = target_organization_id
          and member.user_id = auth.uid()
    );
$$;

create function public.is_organization_manager(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.organization_members as member
        where member.organization_id = target_organization_id
          and member.user_id = auth.uid()
          and member.role in ('owner', 'admin')
    );
$$;

create function public.can_access_listing(target_listing_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.listings as listing
        where listing.id = target_listing_id
          and public.is_organization_member(listing.seller_organization_id)
    );
$$;

create function public.can_access_contract(target_contract_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.contracts as contract
        where contract.id = target_contract_id
          and (
              contract.buyer_user_id = auth.uid()
              or public.is_organization_member(contract.seller_organization_id)
          )
    );
$$;

revoke all on function public.is_organization_member(uuid) from public;
revoke all on function public.is_organization_manager(uuid) from public;
revoke all on function public.can_access_listing(uuid) from public;
revoke all on function public.can_access_contract(uuid) from public;
grant execute on function public.is_organization_member(uuid) to authenticated;
grant execute on function public.is_organization_manager(uuid) to authenticated;
grant execute on function public.can_access_listing(uuid) to authenticated;
grant execute on function public.can_access_contract(uuid) to authenticated;

alter table public.profiles enable row level security;
alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.listings enable row level security;
alter table public.listing_terms enable row level security;
alter table public.listing_versions enable row level security;
alter table public.listing_clauses enable row level security;
alter table public.price_estimates enable row level security;
alter table public.contracts enable row level security;
alter table public.contract_parties enable row level security;
alter table public.contract_terms enable row level security;
alter table public.contract_versions enable row level security;
alter table public.contract_clauses enable row level security;
alter table public.revision_requests enable row level security;
alter table public.revision_request_items enable row level security;
alter table public.documents enable row level security;
alter table public.signature_requests enable row level security;
alter table public.signature_participants enable row level security;
alter table public.provider_events enable row level security;
alter table public.notifications enable row level security;
alter table public.audit_events enable row level security;
alter table public.idempotency_records enable row level security;

create policy profiles_select_own on public.profiles
for select to authenticated using (id = auth.uid());
create policy profiles_insert_own on public.profiles
for insert to authenticated with check (id = auth.uid());
create policy profiles_update_own on public.profiles
for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy organizations_select_member on public.organizations
for select to authenticated using (public.is_organization_member(id));
create policy organizations_update_manager on public.organizations
for update to authenticated
using (public.is_organization_manager(id))
with check (public.is_organization_manager(id));

create policy organization_members_select_self on public.organization_members
for select to authenticated
using (user_id = auth.uid() or public.is_organization_member(organization_id));

create policy listings_select_member on public.listings
for select to authenticated
using (public.is_organization_member(seller_organization_id));
create policy listings_insert_member on public.listings
for insert to authenticated
with check (
    created_by = auth.uid()
    and public.is_organization_member(seller_organization_id)
);
create policy listings_update_member on public.listings
for update to authenticated
using (public.is_organization_member(seller_organization_id))
with check (public.is_organization_member(seller_organization_id));
create policy listings_delete_member on public.listings
for delete to authenticated using (public.is_organization_member(seller_organization_id));

create policy listing_terms_select_allowed on public.listing_terms
for select to authenticated using (public.can_access_listing(listing_id));
create policy listing_terms_write_member on public.listing_terms
for all to authenticated
using (
    exists (
        select 1 from public.listings
        where listings.id = listing_terms.listing_id
          and public.is_organization_member(listings.seller_organization_id)
    )
)
with check (
    exists (
        select 1 from public.listings
        where listings.id = listing_terms.listing_id
          and public.is_organization_member(listings.seller_organization_id)
    )
);
create policy listing_versions_select_allowed on public.listing_versions
for select to authenticated using (public.can_access_listing(listing_id));
create policy listing_versions_insert_member on public.listing_versions
for insert to authenticated
with check (
    exists (
        select 1 from public.listings
        where listings.id = listing_versions.listing_id
          and public.is_organization_member(listings.seller_organization_id)
    )
);
create policy listing_clauses_select_allowed on public.listing_clauses
for select to authenticated
using (
    exists (
        select 1 from public.listing_versions
        where listing_versions.id = listing_clauses.listing_version_id
          and public.can_access_listing(listing_versions.listing_id)
    )
);
create policy listing_clauses_insert_member on public.listing_clauses
for insert to authenticated
with check (
    exists (
        select 1
        from public.listing_versions
        join public.listings on listings.id = listing_versions.listing_id
        where listing_versions.id = listing_clauses.listing_version_id
          and public.is_organization_member(listings.seller_organization_id)
    )
);
create policy price_estimates_select_owner on public.price_estimates
for select to authenticated
using (
    requested_by = auth.uid()
    or exists (
        select 1 from public.listings
        where listings.id = price_estimates.listing_id
          and public.is_organization_member(listings.seller_organization_id)
    )
);

create policy contracts_select_party on public.contracts
for select to authenticated using (public.can_access_contract(id));
create policy contract_parties_select_party on public.contract_parties
for select to authenticated using (public.can_access_contract(contract_id));
create policy contract_terms_select_party on public.contract_terms
for select to authenticated using (public.can_access_contract(contract_id));
create policy contract_versions_select_party on public.contract_versions
for select to authenticated using (public.can_access_contract(contract_id));
create policy contract_clauses_select_party on public.contract_clauses
for select to authenticated
using (
    exists (
        select 1 from public.contract_versions
        where contract_versions.id = contract_clauses.contract_version_id
          and public.can_access_contract(contract_versions.contract_id)
    )
);
create policy revision_requests_select_party on public.revision_requests
for select to authenticated using (public.can_access_contract(contract_id));
create policy revision_request_items_select_party on public.revision_request_items
for select to authenticated
using (
    exists (
        select 1 from public.revision_requests
        where revision_requests.id = revision_request_items.revision_request_id
          and public.can_access_contract(revision_requests.contract_id)
    )
);
create policy documents_select_owner on public.documents
for select to authenticated
using (
    (listing_id is not null and public.can_access_listing(listing_id))
    or (contract_id is not null and public.can_access_contract(contract_id))
);
create policy signature_requests_select_party on public.signature_requests
for select to authenticated using (public.can_access_contract(contract_id));
create policy signature_participants_select_party on public.signature_participants
for select to authenticated
using (
    exists (
        select 1 from public.signature_requests
        where signature_requests.id = signature_participants.signature_request_id
          and public.can_access_contract(signature_requests.contract_id)
    )
);
create policy notifications_select_own on public.notifications
for select to authenticated using (user_id = auth.uid());
create policy notifications_update_own on public.notifications
for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy audit_events_select_party on public.audit_events
for select to authenticated
using (
    (contract_id is not null and public.can_access_contract(contract_id))
    or (
        listing_id is not null
        and exists (
            select 1 from public.listings
            where listings.id = audit_events.listing_id
              and public.is_organization_member(listings.seller_organization_id)
        )
    )
);

revoke all on all tables in schema public from anon;
grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;

comment on function public.can_access_contract(uuid) is
    'RLS helper: true for the individual buyer or a member of the seller organization.';
comment on function public.can_access_listing(uuid) is
    'RLS helper for direct table access by seller members; public reads use FastAPI projection.';
