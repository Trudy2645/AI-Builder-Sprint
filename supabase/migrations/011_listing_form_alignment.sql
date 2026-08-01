alter table public.listings
    add column public_headline text,
    add constraint listings_public_headline_length_check
        check (public_headline is null or char_length(public_headline) <= 1000);

alter table public.listing_terms
    add column supply_quantity_description text,
    add column minimum_quantity integer,
    add column maximum_quantity integer,
    add constraint listing_terms_supply_quantity_description_length_check
        check (
            supply_quantity_description is null
            or char_length(supply_quantity_description) <= 500
        ),
    add constraint listing_terms_minimum_quantity_check
        check (minimum_quantity is null or minimum_quantity > 0),
    add constraint listing_terms_maximum_quantity_check
        check (maximum_quantity is null or maximum_quantity > 0),
    add constraint listing_terms_quantity_range_check
        check (
            minimum_quantity is null or maximum_quantity is null
            or minimum_quantity <= maximum_quantity
        );

comment on column public.listings.public_headline is
    'Seller-authored one-line introduction shown on the public listing card.';
comment on column public.listing_terms.supply_quantity_description is
    'Human-readable supply quantity entered by the seller, such as weekend rooms up to 30.';
comment on column public.listing_terms.minimum_quantity is
    'Minimum billable supply quantity; distinct from the number of travelers.';
comment on column public.listing_terms.maximum_quantity is
    'Maximum billable supply quantity; distinct from the number of travelers.';
