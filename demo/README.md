# Demo Data

The PostgreSQL initialization script in `infrastructure/postgres/init/001-create-demo-databases.sql` creates four databases and seeds the production/development drift scenarios:

- `users.phone`: production contains `NULL`, development requires `NOT NULL`.
- `orders.price`: production is `varchar`, development is `numeric`; one production value is `unknown`.
- `orders.status`: production enum contains `cancelled`, development does not.
- `orders.customer_id`: development adds a foreign key; production contains `999`.
- `users.email`: development adds uniqueness; production contains duplicate `alex@example.com`.
- `customer.full_name` to `customer.display_name`: likely rename.

The dry-run workflow resets `stagebridge_dryrun` on every run and creates audit tables for rejected rows.

