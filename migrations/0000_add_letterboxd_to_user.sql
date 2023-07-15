-- sqlite migration file
-- add a letterboxd_username column to the swap_users table

ALTER TABLE swap_users ADD COLUMN letterboxd_username VARCHAR(64) DEFAULT NULL;
