\set ON_ERROR_STOP on

create schema if not exists migration_test;

create function migration_test.assert_true(condition boolean, message text)
returns void
language plpgsql
as $$
begin
    if not coalesce(condition, false) then
        raise exception 'assertion failed: %', message;
    end if;
end;
$$;

grant usage on schema migration_test to authenticated;
grant execute on function migration_test.assert_true(boolean, text) to authenticated;

select migration_test.assert_true(
    not exists (
        select 1
        from pg_class
        join pg_namespace on pg_namespace.oid = pg_class.relnamespace
        where pg_namespace.nspname = 'public'
          and pg_class.relkind = 'r'
          and not pg_class.relrowsecurity
    ),
    'every public application table must have RLS enabled'
);

select migration_test.assert_true(
    (
        select count(*)
        from pg_indexes
        where schemaname = 'public'
          and indexname in (
              'listings_public_filter_idx',
              'listings_seller_dashboard_idx',
              'contracts_buyer_mypage_idx',
              'contracts_seller_dashboard_idx',
              'notifications_user_unread_idx',
              'knowledge_documents_categories_idx'
          )
    ) = 6,
    'required list and dashboard indexes must exist'
);

insert into auth.users (id, email) values
    ('00000000-0000-0000-0000-000000000001', 'seller@example.test'),
    ('00000000-0000-0000-0000-000000000002', 'buyer@example.test'),
    ('00000000-0000-0000-0000-000000000003', 'stranger@example.test');

insert into public.organizations (
    id,
    organization_type,
    name,
    verification_status,
    verified_at,
    created_by
) values (
    '10000000-0000-0000-0000-000000000001',
    'seller',
    '테스트 셀러',
    'verified',
    timezone('utc', now()),
    '00000000-0000-0000-0000-000000000001'
);

insert into public.profiles (id, username, display_name, active_business_role) values
    ('00000000-0000-0000-0000-000000000001', 'seller', '셀러', 'seller'),
    ('00000000-0000-0000-0000-000000000002', 'buyer', '바이어', 'buyer'),
    ('00000000-0000-0000-0000-000000000003', 'stranger', '제삼자', 'buyer');

insert into public.organization_members (organization_id, user_id, role) values (
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'owner'
);

select set_config(
    'request.jwt.claim.sub',
    '00000000-0000-0000-0000-000000000001',
    false
);
set role authenticated;

select migration_test.assert_true(
    (select count(*) from public.profiles) = 1,
    'a user can read only their own profile'
);

insert into public.listings (
    id,
    seller_organization_id,
    creation_method,
    title,
    district,
    category,
    created_by
) values (
    '20000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'manual',
    '테스트 숙박 공고',
    '해운대구',
    'accommodation',
    '00000000-0000-0000-0000-000000000001'
);

insert into public.listing_versions (
    id,
    listing_id,
    version_no,
    title,
    body,
    content_sha256,
    created_by
) values (
    '21000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    1,
    '테스트 계약',
    '변경되지 않아야 하는 계약 본문',
    repeat('a', 64),
    '00000000-0000-0000-0000-000000000001'
);

update public.listings
set current_version_id = '21000000-0000-0000-0000-000000000001'
where id = '20000000-0000-0000-0000-000000000001';

reset role;

do $$
begin
    begin
        update public.listing_versions
        set body = '덮어쓴 본문'
        where id = '21000000-0000-0000-0000-000000000001';
        raise exception 'immutable listing version update unexpectedly succeeded';
    exception
        when sqlstate '55000' then null;
    end;
end;
$$;

select set_config(
    'request.jwt.claim.sub',
    '00000000-0000-0000-0000-000000000002',
    false
);
set role authenticated;

do $$
begin
    begin
        insert into public.listings (
            seller_organization_id,
            creation_method,
            title,
            district,
            category,
            created_by
        ) values (
            '10000000-0000-0000-0000-000000000001',
            'manual',
            '권한 없는 공고',
            '해운대구',
            'tour',
            '00000000-0000-0000-0000-000000000002'
        );
        raise exception 'non-member listing insert unexpectedly succeeded';
    exception
        when insufficient_privilege then null;
    end;
end;
$$;

reset role;

update public.listings
set status = 'published', published_at = timezone('utc', now())
where id = '20000000-0000-0000-0000-000000000001';

insert into public.contracts (
    id,
    listing_id,
    buyer_user_id,
    seller_organization_id,
    status,
    requested_people,
    signing_capacity
) values (
    '30000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001',
    'draft',
    2,
    'self'
);

select set_config(
    'request.jwt.claim.sub',
    '00000000-0000-0000-0000-000000000002',
    false
);
set role authenticated;
select migration_test.assert_true(
    (select count(*) from public.listings) = 0,
    'published listing tables remain private behind the FastAPI public projection'
);
select migration_test.assert_true(
    (select count(*) from public.contracts) = 1,
    'the individual buyer can read their own contract'
);

reset role;
select set_config(
    'request.jwt.claim.sub',
    '00000000-0000-0000-0000-000000000003',
    false
);
set role authenticated;
select migration_test.assert_true(
    (select count(*) from public.contracts) = 0,
    'an unrelated user cannot read another buyer contract'
);

reset role;

select migration_test.assert_true(
    not exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and column_name in ('password', 'password_hash')
    ),
    'application tables must not store passwords or password hashes'
);

drop schema migration_test cascade;

\echo 'database schema tests passed'
