# Three-Minute Demo Script

## 0:00 - 0:25

Open `http://localhost:5173`. Show the dashboard topology: production is read-only, development is the schema source, and dry run is isolated.

## 0:25 - 0:55

Click **Run analysis**. The backend inspects PostgreSQL catalogs and runs deterministic preflight checks against production data. Point out that AI is not used to detect raw schema differences.

## 0:55 - 1:30

Open the conflict detail view. Show the six seeded findings:

- `users.phone` has nulls but development requires `NOT NULL`.
- `orders.price` changes from text to numeric and includes `unknown`.
- `orders.status` has incompatible enum values.
- `orders.customer_id` has an orphaned reference.
- `users.email` has duplicates before a new unique constraint.
- `customer.full_name` likely maps to `customer.display_name`.

## 1:30 - 2:05

Click **AI plan**. If no API key is configured, the UI labels the result as the deterministic mock provider. Explain that the plan is structured and advisory; it cannot execute arbitrary SQL.

## 2:05 - 2:35

Approve all controlled actions. Show SQL previews for backfill, numeric normalization, enum mapping, orphan rejection, deduplication, renamed column mapping, and validation.

## 2:35 - 3:00

Click **Dry run**. Show the final report:

- dry run passed;
- eight transferred rows;
- three rejected rows;
- zero validation failures;
- every step recorded in the timeline.

