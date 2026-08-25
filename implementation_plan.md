# Implementation Plan — Automatic Exercise Seeding and Admin Creation

This plan aims to fix deployment issues on Railway and Vercel where:
1. No exercises are present in the database because the seed endpoint was protected and required admin authentication.
2. No admin user existed to authenticate and call the seed endpoint, creating a circular dependency.

We will automate table creation, exercise seeding, and admin account setup safely and idempotently on startup.

## Proposed Changes

We will refactor the startup and seeding logic into clean, reusable functions in a new module, integrate them into the startup event, and simplify the admin seed endpoint.

---

### Backend Configuration

#### [MODIFY] [config.py](file:///c:/Users/mohdm/OneDrive/Desktop/osteoarthritis/backend/app/config.py)
* Add optional settings for default admin credentials with safe fallback values:
  * `DEFAULT_ADMIN_EMAIL: str = "admin@oacare.com"`
  * `DEFAULT_ADMIN_PASSWORD: str = "Admin@123"`
  * `DEFAULT_ADMIN_NAME: str = "System Administrator"`

---

### Startup Seeding Utilities

#### [NEW] [seed.py](file:///c:/Users/mohdm/OneDrive/Desktop/osteoarthritis/backend/app/utils/seed.py)
* Implement a new module to handle startup tasks:
  * Configure logging to log actions clearly.
  * Define `create_tables()`: Calls `Base.metadata.create_all(bind=engine)` and logs `"Database tables created"`.
  * Define `seed_exercises(db: Session)`: 
    * Checks the current exercise count.
    * If `count == 0`, combines `KNEE_EXERCISES` and `HIP_EXERCISES`, instantiates them with a `sort_order` incrementing from 1, commits them, and logs `"Seeded XX exercises"`.
    * If exercises already exist, logs `"Exercises already exist"` and does nothing.
    * Returns a status dict for manual seed endpoints.
  * Define `create_default_admin(db: Session)`:
    * Checks if any user with `role == "admin"` exists. If one does, logs `"Default admin already exists"` and returns.
    * Checks if a user with the default admin email already exists (to prevent UniqueConstraint conflicts).
    * Hashes the default admin password using `hash_password()`.
    * Creates the default administrator with `role="admin"`, commits, and logs `"Created default administrator"`.

---

### Main Application Startup Integration

#### [MODIFY] [main.py](file:///c:/Users/mohdm/OneDrive/Desktop/osteoarthritis/backend/app/main.py)
* Import `create_tables`, `seed_exercises`, and `create_default_admin` from `app.utils.seed`.
* Modify the `@app.on_event("startup")` handler:
  1. Call `create_tables()`.
  2. Open a session using `SessionLocal()`.
  3. Run `seed_exercises(db)` and `create_default_admin(db)` inside a `try/finally` block to ensure that database transactions are committed and sessions are always cleanly closed.

---

### Admin Router Seeding Endpoint

#### [MODIFY] [admin.py](file:///c:/Users/mohdm/OneDrive/Desktop/osteoarthritis/backend/app/routers/admin.py)
* Import `seed_exercises` from `app.utils.seed` (aliased as `seed_exercises_db`).
* Update the `POST /admin/seed-exercises` endpoint to call `seed_exercises_db(db)` and return its message, eliminating code duplication.
* Remove direct imports of `KNEE_EXERCISES` and `HIP_EXERCISES`.

---

## Verification Plan

### Automated Verification
* We will verify the changes locally by running the server:
  * Check the logs to ensure "Database tables created", "Seeded 20 exercises", and "Created default administrator" are printed.
  * Attempt to log in with the default admin account:
    * `POST /api/auth/login` with `admin@oacare.com` and `Admin@123`.
  * Verify that subsequent restarts log:
    * "Database tables created"
    * "Exercise count: 20"
    * "Exercises already exist"
    * "Default admin already exists"
  * Test the manual seed endpoint using Swagger (`/docs`):
    * `POST /api/admin/seed-exercises` should return `"Exercises already seeded"`.
