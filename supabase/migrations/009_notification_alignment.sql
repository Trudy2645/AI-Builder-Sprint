alter table public.notifications
    add column dedupe_key text;

create unique index notifications_user_dedupe_unique
    on public.notifications (user_id, dedupe_key)
    where dedupe_key is not null;

create index notifications_user_created_idx
    on public.notifications (user_id, created_at desc, id desc);

comment on column public.notifications.dedupe_key is
    'Optional user-scoped key used to suppress repeated operational notifications.';
