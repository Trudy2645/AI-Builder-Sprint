insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
    (
        'contract-documents', 'contract-documents', false, 20971520,
        array[
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg',
            'image/png'
        ]
    ),
    (
        'listing-assets', 'listing-assets', false, 20971520,
        array['image/jpeg', 'image/png']
    ),
    (
        'business-verification', 'business-verification', false, 20971520,
        array[
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg',
            'image/png'
        ]
    )
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

alter table public.documents
    add column expected_mime_type text,
    add column expected_size_bytes bigint,
    add column expected_content_sha256 text;

update public.documents
set expected_mime_type = coalesce(mime_type, 'application/octet-stream'),
    expected_size_bytes = coalesce(size_bytes, 0),
    expected_content_sha256 = coalesce(
        content_sha256,
        encode(digest('', 'sha256'), 'hex')
    );

alter table public.documents
    alter column expected_mime_type set not null,
    alter column expected_size_bytes set not null,
    alter column expected_content_sha256 set not null,
    add constraint documents_expected_mime_type_check
        check (btrim(expected_mime_type) <> ''),
    add constraint documents_expected_size_bytes_check
        check (expected_size_bytes >= 0),
    add constraint documents_expected_content_sha256_check
        check (expected_content_sha256 ~ '^[0-9a-f]{64}$');

comment on column public.documents.expected_mime_type is
    'Client-declared MIME type retained separately from server-verified mime_type.';
comment on column public.documents.expected_size_bytes is
    'Client-declared byte size retained separately from server-verified size_bytes.';
comment on column public.documents.expected_content_sha256 is
    'Client-declared SHA-256 retained separately from the server-verified content_sha256.';
