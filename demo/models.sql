CREATE TABLE IF NOT EXISTS organisations (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL UNIQUE,
  slug VARCHAR(255) NOT NULL UNIQUE
);
CREATE UNIQUE INDEX IF NOT EXISTS org_slug ON organisations USING btree (slug);

DO $$ BEGIN
  CREATE TYPE USER_ROLE AS ENUM ('guest', 'host', 'admin');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  org INT NOT NULL REFERENCES organisations ON DELETE CASCADE,
  role USER_ROLE NOT NULL,
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  email VARCHAR(255)
);
CREATE UNIQUE INDEX IF NOT EXISTS user_email ON users USING btree (org, email);
CREATE INDEX IF NOT EXISTS user_role ON users USING btree (role);
