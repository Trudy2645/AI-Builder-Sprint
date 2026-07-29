create type public.listing_status as enum (
    'draft', 'processing', 'ready', 'published', 'paused', 'expired', 'archived'
);
create type public.listing_creation_method as enum ('manual', 'upload');
create type public.contract_status as enum (
    'draft', 'seller_review', 'revision_requested', 'signing', 'signed', 'cancelled'
);
create type public.signing_capacity as enum ('self', 'group_representative');
create type public.party_role as enum ('buyer', 'seller');
create type public.revision_status as enum (
    'draft', 'sent', 'accepted', 'rejected', 'partially_accepted', 'countered', 'cancelled'
);
create type public.revision_item_decision as enum (
    'pending', 'accepted', 'rejected', 'countered'
);
create type public.document_purpose as enum (
    'source_contract', 'reference', 'listing_hero', 'draft_pdf',
    'signed_contract', 'audit_trail', 'parsed_artifact'
);
create type public.document_status as enum (
    'pending_upload', 'uploaded', 'processing', 'ready', 'failed'
);
create type public.signature_status as enum (
    'preparing', 'in_progress', 'completed', 'failed', 'cancelled'
);

create table public.listings (
    id uuid primary key default gen_random_uuid(),
    seller_organization_id uuid not null
        references public.organizations(id) on delete restrict,
    status public.listing_status not null default 'draft',
    creation_method public.listing_creation_method not null,
    title text not null check (btrim(title) <> ''),
    display_title text,
    display_company_name text,
    district text not null check (btrim(district) <> ''),
    category public.contract_category not null,
    language public.supported_locale not null default 'ko-KR',
    seller_description text,
    ai_summary text,
    hero_document_id uuid,
    current_version_id uuid,
    popularity_score numeric(12, 4) not null default 0,
    view_count bigint not null default 0 check (view_count >= 0),
    contract_request_count bigint not null default 0
        check (contract_request_count >= 0),
    published_at timestamptz,
    paused_at timestamptz,
    expires_at timestamptz,
    created_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint listings_lifecycle_timestamps_check check (
        (status <> 'published' or published_at is not null)
        and (status <> 'paused' or paused_at is not null)
    )
);

create table public.listing_terms (
    listing_id uuid primary key references public.listings(id) on delete cascade,
    service_start_date date,
    service_end_date date,
    supply_quantity integer check (supply_quantity is null or supply_quantity > 0),
    quantity_unit text,
    base_price_amount_minor bigint
        check (base_price_amount_minor is null or base_price_amount_minor >= 0),
    currency text check (currency is null or currency ~ '^[A-Z]{3}$'),
    price_unit text,
    minimum_people integer check (minimum_people is null or minimum_people > 0),
    maximum_people integer check (maximum_people is null or maximum_people > 0),
    cancellation_policy text,
    refund_policy text,
    settlement_policy text,
    safety_policy text,
    compensation_policy text,
    liability_policy text,
    price_display_basis text,
    contract_availability_note text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint listing_terms_service_period_check check (
        service_start_date is null or service_end_date is null
        or service_start_date <= service_end_date
    ),
    constraint listing_terms_people_range_check check (
        minimum_people is null or maximum_people is null
        or minimum_people <= maximum_people
    )
);

create table public.listing_versions (
    id uuid primary key default gen_random_uuid(),
    listing_id uuid not null references public.listings(id) on delete restrict,
    version_no integer not null check (version_no > 0),
    title text not null,
    body text not null,
    content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
    source_document_id uuid,
    structured_data jsonb not null default '{}'::jsonb,
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default timezone('utc', now()),
    unique (listing_id, version_no)
);

create table public.listing_clauses (
    id uuid primary key default gen_random_uuid(),
    listing_version_id uuid not null
        references public.listing_versions(id) on delete restrict,
    clause_order integer not null check (clause_order > 0),
    clause_key text,
    title text not null,
    body text not null,
    source_page integer check (source_page is null or source_page > 0),
    source_bbox jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    unique (listing_version_id, clause_order)
);

create table public.price_estimates (
    id uuid primary key default gen_random_uuid(),
    listing_id uuid not null references public.listings(id) on delete restrict,
    requested_by uuid references auth.users(id) on delete set null,
    people integer not null check (people > 0),
    service_start_date date not null,
    service_end_date date not null,
    display_currency text not null check (display_currency ~ '^[A-Z]{3}$'),
    amount_minor bigint not null check (amount_minor >= 0),
    calculation_method text not null
        check (calculation_method in ('deterministic', 'historical_adjusted')),
    base_amount_minor bigint not null check (base_amount_minor >= 0),
    base_currency text not null check (base_currency ~ '^[A-Z]{3}$'),
    calculation_metadata jsonb not null default '{}'::jsonb,
    ai_explanation text,
    confidence numeric(5, 4) check (confidence is null or confidence between 0 and 1),
    created_at timestamptz not null default timezone('utc', now()),
    constraint price_estimates_service_period_check
        check (service_start_date <= service_end_date)
);

create table public.contracts (
    id uuid primary key default gen_random_uuid(),
    listing_id uuid references public.listings(id) on delete set null,
    buyer_user_id uuid not null references auth.users(id) on delete restrict,
    buyer_organization_id uuid references public.organizations(id) on delete set null,
    seller_organization_id uuid not null
        references public.organizations(id) on delete restrict,
    status public.contract_status not null default 'draft',
    current_version_id uuid,
    source_listing_version_id uuid
        references public.listing_versions(id) on delete restrict,
    buyer_group_name text,
    requested_people integer not null check (requested_people > 0),
    signing_capacity public.signing_capacity not null default 'self',
    estimated_price_amount_minor bigint
        check (estimated_price_amount_minor is null or estimated_price_amount_minor >= 0),
    estimated_price_currency text
        check (estimated_price_currency is null or estimated_price_currency ~ '^[A-Z]{3}$'),
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    signed_at timestamptz,
    cancelled_at timestamptz,
    constraint contracts_group_signing_check check (
        signing_capacity <> 'group_representative' or buyer_group_name is not null
    ),
    constraint contracts_status_timestamp_check check (
        (status <> 'signed' or signed_at is not null)
        and (status <> 'cancelled' or cancelled_at is not null)
    )
);

create table public.contract_parties (
    id uuid primary key default gen_random_uuid(),
    contract_id uuid not null references public.contracts(id) on delete restrict,
    party_role public.party_role not null,
    user_id uuid references auth.users(id) on delete set null,
    organization_id uuid references public.organizations(id) on delete set null,
    name_snapshot text not null,
    legal_name_snapshot text,
    business_registration_no_snapshot text,
    country_code_snapshot text,
    email_snapshot text,
    phone_snapshot text,
    group_name_snapshot text,
    group_size_snapshot integer
        check (group_size_snapshot is null or group_size_snapshot > 0),
    signing_capacity public.signing_capacity,
    created_at timestamptz not null default timezone('utc', now()),
    unique (contract_id, party_role),
    constraint contract_parties_actor_check check (
        (party_role = 'buyer' and user_id is not null)
        or (party_role = 'seller' and organization_id is not null)
    )
);

create table public.contract_terms (
    contract_id uuid primary key references public.contracts(id) on delete restrict,
    service_start_date date not null,
    service_end_date date not null,
    people integer not null check (people > 0),
    amount_minor bigint check (amount_minor is null or amount_minor >= 0),
    currency text check (currency is null or currency ~ '^[A-Z]{3}$'),
    calculation_snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint contract_terms_service_period_check
        check (service_start_date <= service_end_date)
);

create table public.contract_versions (
    id uuid primary key default gen_random_uuid(),
    contract_id uuid not null references public.contracts(id) on delete restrict,
    version_no integer not null check (version_no > 0),
    title text not null,
    body text not null,
    content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
    source_listing_version_id uuid
        references public.listing_versions(id) on delete restrict,
    created_from_revision_request_id uuid,
    structured_data jsonb not null default '{}'::jsonb,
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default timezone('utc', now()),
    unique (contract_id, version_no)
);

create table public.contract_clauses (
    id uuid primary key default gen_random_uuid(),
    contract_version_id uuid not null
        references public.contract_versions(id) on delete restrict,
    source_listing_clause_id uuid
        references public.listing_clauses(id) on delete set null,
    clause_order integer not null check (clause_order > 0),
    clause_key text,
    title text not null,
    body text not null,
    source_page integer check (source_page is null or source_page > 0),
    source_bbox jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    unique (contract_version_id, clause_order)
);

create table public.revision_requests (
    id uuid primary key default gen_random_uuid(),
    contract_id uuid not null references public.contracts(id) on delete restrict,
    contract_version_id uuid not null
        references public.contract_versions(id) on delete restrict,
    status public.revision_status not null default 'draft',
    requested_by_role public.party_role not null,
    requested_by_user_id uuid not null references auth.users(id) on delete restrict,
    message text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    sent_at timestamptz,
    decided_at timestamptz,
    constraint revision_requests_sent_at_check check (
        status = 'draft' or sent_at is not null
    ),
    constraint revision_requests_decided_at_check check (
        status not in ('accepted', 'rejected', 'partially_accepted', 'countered')
        or decided_at is not null
    )
);

create table public.revision_request_items (
    id uuid primary key default gen_random_uuid(),
    revision_request_id uuid not null
        references public.revision_requests(id) on delete restrict,
    clause_id uuid references public.contract_clauses(id) on delete restrict,
    item_order integer not null check (item_order > 0),
    request_type text not null check (btrim(request_type) <> ''),
    reason text not null check (btrim(reason) <> ''),
    requested_text text not null check (btrim(requested_text) <> ''),
    decision public.revision_item_decision not null default 'pending',
    decision_reason text,
    counter_text text,
    decided_by_user_id uuid references auth.users(id) on delete restrict,
    decided_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (revision_request_id, item_order),
    constraint revision_items_counter_text_check check (
        decision <> 'countered' or counter_text is not null
    ),
    constraint revision_items_decision_metadata_check check (
        decision = 'pending'
        or (decided_by_user_id is not null and decided_at is not null)
    )
);

create table public.documents (
    id uuid primary key default gen_random_uuid(),
    listing_id uuid references public.listings(id) on delete restrict,
    listing_version_id uuid references public.listing_versions(id) on delete restrict,
    contract_id uuid references public.contracts(id) on delete restrict,
    contract_version_id uuid references public.contract_versions(id) on delete restrict,
    purpose public.document_purpose not null,
    status public.document_status not null default 'pending_upload',
    storage_bucket text not null,
    storage_object_path text not null,
    original_filename text,
    mime_type text,
    size_bytes bigint check (size_bytes is null or size_bytes >= 0),
    content_sha256 text check (content_sha256 is null or content_sha256 ~ '^[0-9a-f]{64}$'),
    extracted_data jsonb not null default '{}'::jsonb,
    failure_code text,
    uploaded_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (storage_bucket, storage_object_path),
    constraint documents_owner_check check (
        (listing_id is not null and contract_id is null)
        or (listing_id is null and contract_id is not null)
    ),
    constraint documents_listing_version_check check (
        listing_version_id is null or listing_id is not null
    ),
    constraint documents_contract_version_check check (
        contract_version_id is null or contract_id is not null
    )
);

alter table public.listings
    add constraint listings_hero_document_fk
    foreign key (hero_document_id) references public.documents(id) on delete restrict;
alter table public.listings
    add constraint listings_current_version_fk
    foreign key (current_version_id) references public.listing_versions(id) on delete restrict;
alter table public.listing_versions
    add constraint listing_versions_source_document_fk
    foreign key (source_document_id) references public.documents(id) on delete set null;
alter table public.contracts
    add constraint contracts_current_version_fk
    foreign key (current_version_id) references public.contract_versions(id) on delete restrict;
alter table public.contract_versions
    add constraint contract_versions_revision_request_fk
    foreign key (created_from_revision_request_id)
    references public.revision_requests(id) on delete restrict;

create table public.signature_requests (
    id uuid primary key default gen_random_uuid(),
    contract_id uuid not null references public.contracts(id) on delete restrict,
    contract_version_id uuid not null
        references public.contract_versions(id) on delete restrict,
    status public.signature_status not null default 'preparing',
    provider text not null default 'modusign',
    provider_template_id text,
    provider_document_id text,
    provider_status text,
    current_signing_order integer check (
        current_signing_order is null or current_signing_order > 0
    ),
    signed_document_id uuid references public.documents(id) on delete restrict,
    audit_trail_document_id uuid references public.documents(id) on delete restrict,
    idempotency_key text not null,
    requested_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    completed_at timestamptz,
    failed_at timestamptz,
    unique (contract_id, idempotency_key),
    unique (provider, provider_document_id),
    constraint signature_requests_completed_artifacts_check check (
        status <> 'completed'
        or (
            completed_at is not null
            and signed_document_id is not null
            and audit_trail_document_id is not null
        )
    )
);

create table public.signature_participants (
    id uuid primary key default gen_random_uuid(),
    signature_request_id uuid not null
        references public.signature_requests(id) on delete restrict,
    party_role public.party_role not null,
    provider_role_name text not null,
    signing_order integer not null check (signing_order > 0),
    name_snapshot text not null,
    email_snapshot text not null,
    represents_group_name text,
    represents_group_size integer
        check (represents_group_size is null or represents_group_size > 0),
    representation_confirmed_at timestamptz,
    provider_participant_id text,
    signed_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    unique (signature_request_id, party_role),
    constraint signature_participants_role_name_check check (
        (party_role = 'buyer' and provider_role_name = '바이어')
        or (party_role = 'seller' and provider_role_name = '셀러')
    ),
    constraint signature_participants_representation_check check (
        represents_group_name is null
        or (
            party_role = 'buyer'
            and represents_group_size is not null
            and representation_confirmed_at is not null
        )
    )
);

create table public.provider_events (
    id uuid primary key default gen_random_uuid(),
    provider text not null,
    provider_event_id text not null,
    provider_document_id text,
    event_type text,
    payload_hash text not null check (payload_hash ~ '^[0-9a-f]{64}$'),
    normalized_payload jsonb not null default '{}'::jsonb,
    processed boolean not null default false,
    processing_error text,
    received_at timestamptz not null default timezone('utc', now()),
    processed_at timestamptz,
    unique (provider, provider_event_id)
);

create table public.notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    notification_type text not null,
    title text not null,
    body text not null,
    resource_type text,
    resource_id uuid,
    read_at timestamptz,
    created_at timestamptz not null default timezone('utc', now())
);

create table public.audit_events (
    id uuid primary key default gen_random_uuid(),
    contract_id uuid references public.contracts(id) on delete restrict,
    listing_id uuid references public.listings(id) on delete restrict,
    actor_user_id uuid references auth.users(id) on delete set null,
    actor_role text not null,
    event_type text not null,
    target_type text,
    target_id uuid,
    event_data jsonb not null default '{}'::jsonb,
    request_id text,
    created_at timestamptz not null default timezone('utc', now()),
    constraint audit_events_owner_check check (
        contract_id is not null or listing_id is not null
    )
);

create table public.idempotency_records (
    id uuid primary key default gen_random_uuid(),
    actor_user_id uuid references auth.users(id) on delete cascade,
    organization_id uuid references public.organizations(id) on delete cascade,
    operation text not null,
    idempotency_key text not null,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    response_status integer,
    response_body jsonb,
    resource_type text,
    resource_id uuid,
    created_at timestamptz not null default timezone('utc', now()),
    expires_at timestamptz not null,
    constraint idempotency_actor_check check (
        actor_user_id is not null or organization_id is not null
    )
);

create unique index idempotency_records_user_unique
    on public.idempotency_records (actor_user_id, operation, idempotency_key)
    where actor_user_id is not null;
create unique index idempotency_records_organization_unique
    on public.idempotency_records (organization_id, operation, idempotency_key)
    where organization_id is not null;

create trigger listings_set_updated_at before update on public.listings
for each row execute function public.set_updated_at();
create trigger listing_terms_set_updated_at before update on public.listing_terms
for each row execute function public.set_updated_at();
create trigger contracts_set_updated_at before update on public.contracts
for each row execute function public.set_updated_at();
create trigger contract_terms_set_updated_at before update on public.contract_terms
for each row execute function public.set_updated_at();
create trigger revision_requests_set_updated_at before update on public.revision_requests
for each row execute function public.set_updated_at();
create trigger revision_request_items_set_updated_at
before update on public.revision_request_items
for each row execute function public.set_updated_at();
create trigger documents_set_updated_at before update on public.documents
for each row execute function public.set_updated_at();
create trigger signature_requests_set_updated_at before update on public.signature_requests
for each row execute function public.set_updated_at();

comment on table public.listings is
    'Seller marketplace listings shared by many potential buyers.';
comment on table public.contracts is
    'A negotiated contract between one individual buyer and one seller organization.';
comment on table public.contract_versions is
    'Immutable contract snapshots; create a new row for every negotiated change.';
comment on table public.audit_events is
    'Append-only audit history without secrets or complete contract source text.';
