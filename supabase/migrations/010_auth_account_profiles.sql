alter table public.profiles
    add column affiliation_name text,
    add column business_type text;

alter table public.organizations
    add column representative_name text,
    add column business_address text,
    add column supply_categories public.contract_category[] not null
        default '{}'::public.contract_category[];

alter table public.organization_members
    add column job_title text;

alter type public.document_purpose
    add value if not exists 'business_verification';

alter table public.documents
    add column organization_id uuid
        references public.organizations(id) on delete restrict;

alter table public.documents
    drop constraint documents_owner_check,
    add constraint documents_owner_check check (
        num_nonnulls(organization_id, listing_id, contract_id) = 1
    );

create index documents_organization_idx
    on public.documents (organization_id, purpose, created_at desc)
    where organization_id is not null;

drop policy documents_select_owner on public.documents;
create policy documents_select_owner on public.documents
for select to authenticated
using (
    (organization_id is not null and public.is_organization_member(organization_id))
    or (listing_id is not null and public.can_access_listing(listing_id))
    or (contract_id is not null and public.can_access_contract(contract_id))
);

alter table public.profiles
    add constraint profiles_affiliation_name_check
        check (affiliation_name is null or length(affiliation_name) <= 200),
    add constraint profiles_business_type_check
        check (business_type is null or length(business_type) <= 80);

alter table public.organizations
    add constraint organizations_representative_name_check
        check (representative_name is null or length(representative_name) <= 120),
    add constraint organizations_business_address_check
        check (business_address is null or length(business_address) <= 500),
    add constraint organizations_supply_categories_count_check
        check (cardinality(supply_categories) <= 4);

alter table public.organization_members
    add constraint organization_members_job_title_check
        check (job_title is null or length(job_title) <= 120);

comment on column public.profiles.affiliation_name is
    'Optional buyer affiliation; it does not create a buyer organization or change the contract party.';
comment on column public.profiles.business_type is
    'Optional buyer business context such as agency, inbound operator, or OTA.';
comment on column public.organizations.representative_name is
    'Seller legal representative name used for organization profile and contract snapshots.';
comment on column public.organizations.business_address is
    'Seller business address.';
comment on column public.organizations.supply_categories is
    'Tourism product categories supplied by the seller organization.';
comment on column public.organization_members.job_title is
    'Organization-specific title of the member.';
comment on column public.documents.organization_id is
    'Seller organization owner for business verification documents.';
