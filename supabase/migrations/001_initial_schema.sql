create extension if not exists pgcrypto;

create type public.supported_locale as enum (
    'ko-KR',
    'en-US',
    'ja-JP',
    'zh-CN'
);

create type public.organization_type as enum ('buyer', 'seller');
create type public.verification_status as enum ('pending', 'verified', 'rejected');
create type public.organization_member_role as enum ('owner', 'admin', 'member');
create type public.business_role as enum ('buyer', 'seller');
create type public.contract_category as enum (
    'vehicle_rental',
    'activity',
    'tour',
    'accommodation'
);

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

create function public.prevent_immutable_change()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    raise exception '% rows are immutable', tg_table_name
        using errcode = '55000';
end;
$$;

create table public.organizations (
    id uuid primary key default gen_random_uuid(),
    organization_type public.organization_type not null default 'seller',
    name text not null check (btrim(name) <> ''),
    legal_name text,
    business_registration_no text,
    verification_status public.verification_status not null default 'pending',
    verification_note text,
    rating_average numeric(3, 2) not null default 0
        check (rating_average between 0 and 5),
    rating_count integer not null default 0 check (rating_count >= 0),
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    verified_at timestamptz,
    constraint organizations_verified_at_check check (
        verification_status <> 'verified' or verified_at is not null
    )
);

create unique index organizations_business_registration_no_unique
    on public.organizations (business_registration_no)
    where business_registration_no is not null;

create table public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    username text not null check (btrim(username) <> ''),
    display_name text not null check (btrim(display_name) <> ''),
    phone text,
    country_code text check (country_code is null or country_code ~ '^[A-Z]{2}$'),
    locale public.supported_locale not null default 'ko-KR',
    preferred_currency text not null default 'KRW'
        check (preferred_currency ~ '^[A-Z]{3}$'),
    default_group_name text,
    active_organization_id uuid references public.organizations(id) on delete set null,
    active_business_role public.business_role not null default 'buyer',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index profiles_username_case_insensitive_unique
    on public.profiles (lower(username));

create table public.organization_members (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role public.organization_member_role not null default 'member',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (organization_id, user_id)
);

create index organization_members_user_id_idx
    on public.organization_members (user_id, organization_id);

create trigger organizations_set_updated_at
before update on public.organizations
for each row execute function public.set_updated_at();

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger organization_members_set_updated_at
before update on public.organization_members
for each row execute function public.set_updated_at();

comment on table public.profiles is
    'Application profile extending auth.users; credentials remain in Supabase Auth.';
comment on table public.organizations is
    'Seller organizations and legacy buyer organizations.';
